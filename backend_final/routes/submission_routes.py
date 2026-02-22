import os
import uuid
import aiofiles
import traceback
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import models
import schemas
from auth import get_current_user
from database import get_db
from services.ai_service import (
    evaluate_submission, generate_adaptive_pathway,
    detect_ai_generated, analyze_confidence,
    get_fallback_evaluation
)
from services.anticheat_service import analyze_submission
from services.whisper_service import transcribe_audio
from config import settings

router = APIRouter(prefix="/api/submissions", tags=["Submissions"])


@router.post("", response_model=dict)
def submit_assessment(
    data: schemas.SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Fetch assessment
    assessment = db.query(models.Assessment).filter(
        models.Assessment.id == data.assessment_id,
        models.Assessment.is_active == True
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Get PDF source text
    source_text = ""
    if assessment.pdf_id:
        pdf = db.query(models.PDF).filter(models.PDF.id == assessment.pdf_id).first()
        if pdf:
            source_text = pdf.extracted_text or ""

    # Get previous submissions for originality check
    prev_submissions = db.query(models.Submission).filter(
        models.Submission.assessment_id == data.assessment_id,
        models.Submission.user_id != current_user.id
    ).limit(20).all()
    prev_answers = [s.answers or {} for s in prev_submissions]

    questions = assessment.questions or []

    # ─── AI Evaluation (with fallback) ────────────────────────────────────────
    try:
        scores, feedback, total_score = evaluate_submission(
            questions=questions,
            answers=data.answers,
            pdf_text=source_text,
            language=assessment.language
        )
    except Exception as e:
        print(f"Evaluation error (using fallback): {e}")
        traceback.print_exc()
        scores, feedback, total_score = get_fallback_evaluation(questions, data.answers)

    # ─── AI Detection (best effort, non-blocking) ────────────────────────────
    ai_detection_results = {}
    try:
        ai_detection_results = detect_ai_generated(data.answers)
    except Exception as e:
        print(f"AI detection error (skipping): {e}")

    # ─── Anti-cheat analysis ─────────────────────────────────────────────────
    anticheat = data.anticheat_flags or {}
    proctoring = data.proctoring_data or {}
    try:
        flags = analyze_submission(
            answers=data.answers,
            source_text=source_text,
            tab_switches=anticheat.get("tab_switches", 0),
            copy_paste_count=anticheat.get("copy_paste_count", 0),
            previous_submissions_answers=prev_answers,
            ai_detection_results=ai_detection_results
        )
    except Exception as e:
        print(f"Anticheat error (using defaults): {e}")
        flags = {"risk_level": "low", "overall_integrity_score": 100, "flags_triggered": [], "ai_detection": {}}

    # ─── Confidence Analysis (best effort) ────────────────────────────────────
    confidence_scores = {}
    try:
        confidence_scores = analyze_confidence(data.answers)
    except Exception as e:
        print(f"Confidence analysis error (skipping): {e}")

    # ─── Save submission ──────────────────────────────────────────────────────
    try:
        submission = models.Submission(
            user_id=current_user.id,
            assessment_id=data.assessment_id,
            answers=data.answers,
            scores=scores,
            feedback=feedback,
            total_score=total_score,
            max_score=100.0,
            time_taken_seconds=data.time_taken_seconds,
            anticheat_flags=flags,
            evaluated_at=datetime.utcnow()
        )
        db.add(submission)

        # Update user XP
        xp_gain = max(5, int(total_score / 10) * 10)
        current_user.xp_points = (current_user.xp_points or 0) + xp_gain
        current_user.last_active = datetime.utcnow()

        db.commit()
        db.refresh(submission)
    except Exception as e:
        db.rollback()
        print(f"DB save error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save submission: {str(e)}")

    # ─── Adaptive Pathway (best effort) ───────────────────────────────────────
    pathway = {}
    try:
        other_assessments = db.query(models.Assessment).filter(
            models.Assessment.id != data.assessment_id,
            models.Assessment.is_active == True
        ).limit(10).all()
        topic_list = [a.title for a in other_assessments]

        # Find weakest answers
        weakest_answers = {}
        if scores:
            scored_indices = []
            for q_idx, q_scores in scores.items():
                if isinstance(q_scores, dict):
                    core = [v for k, v in q_scores.items() if k != "confidence"]
                    avg = sum(core) / max(1, len(core))
                    scored_indices.append((q_idx, avg))
            scored_indices.sort(key=lambda x: x[1])
            for q_idx, _ in scored_indices[:3]:
                weakest_answers[q_idx] = data.answers.get(q_idx, "")

        pathway = generate_adaptive_pathway(
            scores=scores,
            questions=questions,
            available_topics=topic_list,
            assessment_title=assessment.title,
            weakest_answers=weakest_answers
        )

        # Save pathway step
        pathway_step = models.PathwayStep(
            user_id=current_user.id,
            source_assessment_id=data.assessment_id,
            reason=pathway.get("reason", ""),
            skill_gaps=pathway.get("skill_gaps", []),
            recommended_topics=pathway.get("recommended_topics", [])
        )
        db.add(pathway_step)
        db.commit()
    except Exception as e:
        print(f"Pathway error (skipping): {e}")
        traceback.print_exc()
        pathway = {
            "skill_gaps": ["Analysis needs improvement"],
            "recommended_activities": ["Review the material and try again"],
            "reason": "Pathway generation encountered an issue. Review your weak areas manually.",
            "next_difficulty": "intermediate"
        }

    return {
        "submission_id": submission.id,
        "total_score": total_score,
        "scores": scores,
        "feedback": feedback,
        "confidence_scores": confidence_scores,
        "anticheat": {
            "risk_level": flags.get("risk_level", "low"),
            "integrity_score": flags.get("overall_integrity_score", 100),
            "flags": flags.get("flags_triggered", []),
            "ai_detection": flags.get("ai_detection", {})
        },
        "xp_gained": max(5, int(total_score / 10) * 10),
        "pathway": pathway,
        "proctoring": proctoring,
        "message": "Assessment submitted and evaluated successfully!"
    }


@router.post("/{submission_id}/audio")
async def upload_audio_response(
    submission_id: int,
    audio_file: UploadFile = File(...),
    question_index: int = Form(0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    submission = db.query(models.Submission).filter(
        models.Submission.id == submission_id,
        models.Submission.user_id == current_user.id
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Save file
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = audio_file.filename.split(".")[-1] if "." in audio_file.filename else "webm"
    audio_filename = f"audio_{uuid.uuid4()}.{ext}"
    audio_path = os.path.join(settings.UPLOAD_DIR, audio_filename)

    content = await audio_file.read()
    async with aiofiles.open(audio_path, "wb") as f:
        await f.write(content)

    # Transcribe
    assessment = db.query(models.Assessment).filter(
        models.Assessment.id == submission.assessment_id
    ).first()
    lang = assessment.language if assessment else "en"
    transcription = transcribe_audio(audio_path, language=lang)

    transcript_text = transcription.get("text", "")
    submission.audio_transcript = (submission.audio_transcript or "") + \
        f"\n[Q{question_index+1}]: {transcript_text}"

    answers = dict(submission.answers or {})
    answers[str(question_index)] = transcript_text
    submission.answers = answers

    db.commit()

    return {
        "transcript": transcript_text,
        "language_detected": transcription.get("language", lang),
        "message": "Audio transcribed successfully"
    }


@router.get("/mine")
def get_my_submissions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    submissions = db.query(models.Submission).filter(
        models.Submission.user_id == current_user.id
    ).order_by(models.Submission.submitted_at.desc()).all()

    result = []
    for s in submissions:
        assessment = db.query(models.Assessment).filter(
            models.Assessment.id == s.assessment_id
        ).first()
        cert = db.query(models.Certificate).filter(
            models.Certificate.submission_id == s.id
        ).first()

        result.append({
            "id": s.id,
            "assessment_id": s.assessment_id,
            "assessment_title": assessment.title if assessment else "Unknown",
            "assessment_emoji": assessment.thumbnail_emoji if assessment else "📚",
            "total_score": s.total_score,
            "submitted_at": s.submitted_at,
            "has_certificate": cert is not None,
            "certificate_id": cert.id if cert else None,
            "risk_level": (s.anticheat_flags or {}).get("risk_level", "low")
        })

    return result


@router.get("/{submission_id}")
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = db.query(models.Submission).filter(models.Submission.id == submission_id)
    if current_user.role != "admin":
        query = query.filter(models.Submission.user_id == current_user.id)

    submission = query.first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    return {
        "id": submission.id,
        "user_id": submission.user_id,
        "assessment_id": submission.assessment_id,
        "answers": submission.answers,
        "scores": submission.scores,
        "feedback": submission.feedback,
        "total_score": submission.total_score,
        "time_taken_seconds": submission.time_taken_seconds,
        "anticheat_flags": submission.anticheat_flags,
        "audio_transcript": submission.audio_transcript,
        "submitted_at": submission.submitted_at,
        "evaluated_at": submission.evaluated_at
    }
