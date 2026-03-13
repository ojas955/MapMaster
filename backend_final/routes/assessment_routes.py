import os
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import models
import schemas
from auth import get_current_user, get_current_admin
from database import get_db
from services.ai_service import generate_followup_question
from services.visual_capture_service import enrich_question_for_capture, process_visual_capture, question_requires_visual_capture
from config import settings

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])


# ─── Schema for follow-up request ─────────────────────────────────────────────
class FollowupRequest(BaseModel):
    question_index: int
    student_answer: str


@router.get("", response_model=List[dict])
def list_assessments(
    difficulty: Optional[str] = None,
    language: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = db.query(models.Assessment).filter(models.Assessment.is_active == True)

    if difficulty:
        query = query.filter(models.Assessment.difficulty == difficulty)
    if language:
        query = query.filter(models.Assessment.language == language)
    if category:
        query = query.filter(models.Assessment.category == category)

    assessments = query.order_by(models.Assessment.created_at.desc()).all()

    result = []
    for a in assessments:
        questions = a.questions or []
        submission_count = db.query(models.Submission).filter(
            models.Submission.assessment_id == a.id
        ).count()
        user_submitted = db.query(models.Submission).filter(
            models.Submission.assessment_id == a.id,
            models.Submission.user_id == current_user.id
        ).first() is not None

        result.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "difficulty": a.difficulty,
            "category": a.category,
            "time_limit_minutes": a.time_limit_minutes,
            "language": a.language,
            "tags": a.tags or [],
            "thumbnail_emoji": a.thumbnail_emoji,
            "num_questions": len(questions),
            "has_capture_questions": any(question_requires_visual_capture(q)[0] for q in questions),
            "created_at": a.created_at,
            "submission_count": submission_count,
            "user_submitted": user_submitted
        })

    return result


@router.get("/{assessment_id}")
def get_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    assessment = db.query(models.Assessment).filter(
        models.Assessment.id == assessment_id,
        models.Assessment.is_active == True
    ).first()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    enriched_questions = [enrich_question_for_capture(q) for q in (assessment.questions or [])]

    return {
        "id": assessment.id,
        "title": assessment.title,
        "description": assessment.description,
        "questions": enriched_questions,
        "difficulty": assessment.difficulty,
        "category": assessment.category,
        "time_limit_minutes": assessment.time_limit_minutes,
        "language": assessment.language,
        "tags": assessment.tags or [],
        "thumbnail_emoji": assessment.thumbnail_emoji,
        "created_at": assessment.created_at,
        "pdf_id": assessment.pdf_id
    }


# ─── Dynamic Follow-up Question ──────────────────────────────────────────────
@router.post("/{assessment_id}/followup")
def get_followup_question(
    assessment_id: int,
    data: FollowupRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Generate a dynamic follow-up question based on student's answer."""
    assessment = db.query(models.Assessment).filter(
        models.Assessment.id == assessment_id,
        models.Assessment.is_active == True
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    questions = assessment.questions or []
    if data.question_index < 0 or data.question_index >= len(questions):
        raise HTTPException(status_code=400, detail="Invalid question index")

    original_q = questions[data.question_index]

    # Get PDF context for better follow-ups
    pdf_context = ""
    if assessment.pdf_id:
        pdf = db.query(models.PDF).filter(models.PDF.id == assessment.pdf_id).first()
        if pdf:
            pdf_context = pdf.extracted_text or ""

    followup = generate_followup_question(
        original_question=original_q.get("text", ""),
        student_answer=data.student_answer,
        pdf_context=pdf_context,
        language=assessment.language
    )

    if not followup:
        return {
            "followup": None,
            "message": "No follow-up generated"
        }

    return {
        "followup": followup,
        "original_question_index": data.question_index,
        "message": "Follow-up question generated!"
    }


@router.post("/{assessment_id}/questions/{question_index}/capture")
async def upload_visual_capture(
    assessment_id: int,
    question_index: int,
    background_tasks: BackgroundTasks,
    capture_file: UploadFile = File(...),
    typed_context: str = Form(""),
    device_label: str = Form(""),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    assessment = db.query(models.Assessment).filter(
        models.Assessment.id == assessment_id,
        models.Assessment.is_active == True
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    questions = assessment.questions or []
    if question_index < 0 or question_index >= len(questions):
        raise HTTPException(status_code=400, detail="Invalid question index")

    capture_required, capture_mode = question_requires_visual_capture(questions[question_index])
    if not capture_required:
        raise HTTPException(status_code=400, detail="This question does not require visual capture")

    content = await capture_file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty capture file")

    capture_dir = os.path.join(settings.UPLOAD_DIR, "whiteboard_captures")
    os.makedirs(capture_dir, exist_ok=True)
    ext = os.path.splitext(capture_file.filename or "capture.jpg")[1] or ".jpg"
    filename = f"capture_{uuid.uuid4().hex}{ext}"
    image_path = os.path.join(capture_dir, filename)
    with open(image_path, "wb") as saved:
        saved.write(content)

    capture = models.VisualCapture(
        user_id=current_user.id,
        assessment_id=assessment_id,
        question_index=question_index,
        image_path=image_path,
        mime_type=capture_file.content_type or "image/jpeg",
        device_label=device_label[:255],
        typed_context=typed_context,
        status="processing",
    )
    db.add(capture)
    db.commit()
    db.refresh(capture)

    background_tasks.add_task(process_visual_capture, capture.id)

    return {
        "capture_id": capture.id,
        "question_index": question_index,
        "capture_mode": capture_mode,
        "status": capture.status,
        "message": "Capture uploaded. Analysis is running in the background."
    }


@router.get("/{assessment_id}/captures/me")
def get_my_visual_captures(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    captures = db.query(models.VisualCapture).filter(
        models.VisualCapture.assessment_id == assessment_id,
        models.VisualCapture.user_id == current_user.id
    ).order_by(models.VisualCapture.created_at.desc()).all()

    latest_by_question = {}
    for capture in captures:
        q_key = str(capture.question_index)
        if q_key in latest_by_question:
            continue
        latest_by_question[q_key] = {
            "capture_id": capture.id,
            "question_index": capture.question_index,
            "status": capture.status,
            "analysis_summary": capture.analysis_summary,
            "extracted_text": capture.extracted_text,
            "scores": capture.scores,
            "feedback": capture.feedback,
            "overall_score": capture.overall_score,
            "device_label": capture.device_label,
            "evaluator_used": capture.evaluator_used,
            "created_at": capture.created_at,
        }

    return list(latest_by_question.values())


@router.post("")
def create_assessment(
    data: schemas.AssessmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin)
):
    assessment = models.Assessment(
        title=data.title,
        description=data.description,
        questions=[q.model_dump() for q in data.questions],
        difficulty=data.difficulty,
        category=data.category,
        time_limit_minutes=data.time_limit_minutes,
        language=data.language,
        created_by=current_user.id,
        tags=data.tags,
        thumbnail_emoji=data.thumbnail_emoji
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return {"id": assessment.id, "message": "Assessment created successfully"}


@router.post("/demo/whiteboard")
def create_whiteboard_demo_assessment(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin)
):
    assessment = models.Assessment(
        title="Whiteboard Interview Simulation — Diagram & Commands",
        description="Demo assessment for handwritten diagrams, flowcharts, commands, and step-by-step white-paper interview answers.",
        questions=[
            {
                "id": 1,
                "text": "Draw a simple flowchart showing how an HTTP request travels from browser to backend server to database and back to the browser. Label the important steps.",
                "type": "whiteboard_capture",
                "bloom_level": "analyze",
                "section_reference": "System Design Basics",
                "max_score": 10,
                "rubric": {
                    "depth": "Covers browser, server, database, and response path clearly",
                    "accuracy": "Sequence and components are technically correct",
                    "application": "Uses a realistic request-response example",
                    "originality": "Clear layout and meaningful annotations"
                }
            },
            {
                "id": 2,
                "text": "On white paper, write the Linux commands you would use to create a folder, move into it, create a Python virtual environment, activate it, and install requirements.",
                "type": "commands",
                "bloom_level": "apply",
                "section_reference": "CLI Workflow",
                "max_score": 10,
                "rubric": {
                    "depth": "Includes the complete command sequence",
                    "accuracy": "Commands are syntactically correct",
                    "application": "Shows the correct order of execution",
                    "originality": "Uses practical command-line context"
                }
            },
            {
                "id": 3,
                "text": "Explain in text why an external camera can be useful for interview whiteboard rounds and what best practices improve capture quality.",
                "type": "open_ended",
                "bloom_level": "evaluate",
                "section_reference": "Interview Preparation",
                "max_score": 10,
                "rubric": {
                    "depth": "Gives multiple reasons and trade-offs",
                    "accuracy": "Advice is realistic and technically correct",
                    "application": "Mentions lighting, framing, and readability",
                    "originality": "Shows practical interview awareness"
                }
            }
        ],
        difficulty="intermediate",
        category="Interview Simulation",
        time_limit_minutes=20,
        language="en",
        created_by=current_user.id,
        tags=["whiteboard", "diagram", "commands", "camera"],
        thumbnail_emoji="🧾"
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return {
        "id": assessment.id,
        "message": "Whiteboard demo assessment created successfully"
    }


@router.delete("/{assessment_id}")
def delete_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin)
):
    assessment = db.query(models.Assessment).filter(models.Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    assessment.is_active = False
    db.commit()
    return {"message": "Assessment deactivated"}
