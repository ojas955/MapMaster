from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import models
from auth import get_current_user, get_current_admin
from database import get_db

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/me")
def my_analytics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    submissions = db.query(models.Submission).filter(
        models.Submission.user_id == current_user.id
    ).order_by(models.Submission.submitted_at.desc()).all()

    if not submissions:
        return {
            "total_submissions": 0,
            "average_score": 0,
            "best_score": 0,
            "xp_points": current_user.xp_points or 0,
            "streak_days": current_user.streak_days or 0,
            "skill_radar": {
                "labels": ["Depth", "Accuracy", "Application", "Originality"],
                "scores": [0, 0, 0, 0]
            },
            "recent_submissions": [],
            "pathway_steps": [],
            "score_history": []
        }

    scores = [s.total_score for s in submissions]
    avg_score = sum(scores) / len(scores) if scores else 0
    best_score = max(scores) if scores else 0

    # Aggregate rubric skill scores
    rubric_totals = {"depth": 0, "accuracy": 0, "application": 0, "originality": 0}
    rubric_count = 0
    for s in submissions:
        if s.scores:
            for q_scores in s.scores.values():
                if isinstance(q_scores, dict):
                    for k in rubric_totals:
                        rubric_totals[k] += q_scores.get(k, 0)
                    rubric_count += 1

    radar_scores = []
    if rubric_count > 0:
        radar_scores = [
            round((rubric_totals[k] / rubric_count) * 10, 1)
            for k in ["depth", "accuracy", "application", "originality"]
        ]
    else:
        radar_scores = [0, 0, 0, 0]

    # Recent submissions
    recent = []
    for s in submissions[:5]:
        a = db.query(models.Assessment).filter(models.Assessment.id == s.assessment_id).first()
        recent.append({
            "id": s.id,
            "assessment_title": a.title if a else "Unknown",
            "emoji": a.thumbnail_emoji if a else "📚",
            "total_score": s.total_score,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else ""
        })

    # Score history (last 10)
    score_history = [
        {
            "date": s.submitted_at.strftime("%m/%d") if s.submitted_at else "",
            "score": s.total_score
        }
        for s in reversed(submissions[:10])
    ]

    # Pathway steps
    pathway_steps = db.query(models.PathwayStep).filter(
        models.PathwayStep.user_id == current_user.id
    ).order_by(models.PathwayStep.created_at.desc()).limit(3).all()

    steps = [
        {
            "id": p.id,
            "skill_gaps": p.skill_gaps or [],
            "recommended_topics": p.recommended_topics or [],
            "reason": p.reason,
            "created_at": p.created_at.isoformat() if p.created_at else "",
            "is_completed": p.is_completed
        }
        for p in pathway_steps
    ]

    return {
        "total_submissions": len(submissions),
        "average_score": round(avg_score, 1),
        "best_score": round(best_score, 1),
        "xp_points": current_user.xp_points or 0,
        "streak_days": current_user.streak_days or 0,
        "skill_radar": {
            "labels": ["Depth", "Accuracy", "Application", "Originality"],
            "scores": radar_scores
        },
        "recent_submissions": recent,
        "pathway_steps": steps,
        "score_history": score_history
    }


@router.get("/group/{assessment_id}")
def group_analytics(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin)
):
    assessment = db.query(models.Assessment).filter(
        models.Assessment.id == assessment_id
    ).first()
    if not assessment:
        return {"error": "Assessment not found"}

    submissions = db.query(models.Submission).filter(
        models.Submission.assessment_id == assessment_id
    ).all()

    if not submissions:
        return {
            "assessment_id": assessment_id,
            "assessment_title": assessment.title,
            "total_participants": 0,
            "average_score": 0,
            "score_distribution": {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0},
            "question_averages": []
        }

    scores = [s.total_score for s in submissions]
    avg = sum(scores) / len(scores) if scores else 0

    # Score distribution
    distribution = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for score in scores:
        if score <= 20:
            distribution["0-20"] += 1
        elif score <= 40:
            distribution["21-40"] += 1
        elif score <= 60:
            distribution["41-60"] += 1
        elif score <= 80:
            distribution["61-80"] += 1
        else:
            distribution["81-100"] += 1

    # Per-question averages
    q_totals = {}
    q_counts = {}
    for s in submissions:
        if s.scores:
            for q_idx, q_scores in s.scores.items():
                if isinstance(q_scores, dict):
                    avg_q = sum(q_scores.values()) / len(q_scores)
                    q_totals[q_idx] = q_totals.get(q_idx, 0) + avg_q
                    q_counts[q_idx] = q_counts.get(q_idx, 0) + 1

    q_averages = [
        round(q_totals[k] / q_counts[k] * 10, 1)
        for k in sorted(q_totals.keys())
    ]

    return {
        "assessment_id": assessment_id,
        "assessment_title": assessment.title,
        "total_participants": len(submissions),
        "average_score": round(avg, 1),
        "score_distribution": distribution,
        "question_averages": q_averages
    }


@router.get("/admin/overview")
def admin_overview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin)
):
    total_users = db.query(models.User).filter(models.User.role == "student").count()
    total_assessments = db.query(models.Assessment).filter(models.Assessment.is_active == True).count()
    total_submissions = db.query(models.Submission).count()
    total_certs = db.query(models.Certificate).filter(models.Certificate.is_valid == True).count()

    all_scores = db.query(models.Submission.total_score).all()
    avg_platform_score = sum(s[0] for s in all_scores) / len(all_scores) if all_scores else 0

    top_students = db.query(models.User).filter(
        models.User.role == "student"
    ).order_by(models.User.xp_points.desc()).limit(5).all()

    return {
        "total_users": total_users,
        "total_assessments": total_assessments,
        "total_submissions": total_submissions,
        "total_certificates": total_certs,
        "avg_platform_score": round(avg_platform_score, 1),
        "top_students": [
            {"name": u.name, "xp": u.xp_points, "email": u.email}
            for u in top_students
        ]
    }
