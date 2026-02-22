from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import models
import schemas
from auth import get_current_user, get_current_admin
from database import get_db
from services.ai_service import generate_followup_question

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
            "num_questions": len(a.questions) if a.questions else 0,
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

    return {
        "id": assessment.id,
        "title": assessment.title,
        "description": assessment.description,
        "questions": assessment.questions,
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
