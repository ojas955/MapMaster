import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import models
import schemas
from auth import get_current_user
from database import get_db
from services.certificate_service import generate_certificate
from config import settings

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


@router.post("/generate/{submission_id}")
def generate_cert(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Fetch submission
    submission = db.query(models.Submission).filter(
        models.Submission.id == submission_id,
        models.Submission.user_id == current_user.id
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Check if cert already exists
    existing = db.query(models.Certificate).filter(
        models.Certificate.submission_id == submission_id
    ).first()
    if existing:
        return {
            "id": existing.id,
            "qr_hash": existing.qr_hash,
            "cert_url": f"{settings.BACKEND_URL}/api/certificates/download/{existing.qr_hash}",
            "issued_at": existing.issued_at,
            "message": "Certificate already issued"
        }

    # Get assessment title
    assessment = db.query(models.Assessment).filter(
        models.Assessment.id == submission.assessment_id
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Minimum score to issue certificate
    if submission.total_score < 40:
        raise HTTPException(
            status_code=400,
            detail=f"Score of {submission.total_score:.1f}% is below the minimum 40% required for a certificate"
        )

    # Generate certificate image
    try:
        cert_filename, qr_hash = generate_certificate(
            user_name=current_user.name,
            assessment_title=assessment.title,
            score=submission.total_score,
            submission_id=submission.id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Certificate generation failed: {str(e)}")

    # Save certificate record
    cert = models.Certificate(
        user_id=current_user.id,
        submission_id=submission_id,
        cert_filename=cert_filename,
        qr_hash=qr_hash,
        is_valid=True
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)

    return {
        "id": cert.id,
        "qr_hash": qr_hash,
        "cert_url": f"{settings.BACKEND_URL}/api/certificates/download/{qr_hash}",
        "issued_at": cert.issued_at,
        "score": submission.total_score,
        "message": "Certificate generated successfully! 🎉"
    }


@router.get("/download/{qr_hash}")
def download_certificate(qr_hash: str, db: Session = Depends(get_db)):
    cert = db.query(models.Certificate).filter(
        models.Certificate.qr_hash == qr_hash,
        models.Certificate.is_valid == True
    ).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found or invalid")

    cert_path = os.path.join(settings.CERT_DIR, cert.cert_filename)
    if not os.path.exists(cert_path):
        raise HTTPException(status_code=404, detail="Certificate file not found")

    return FileResponse(
        cert_path,
        media_type="image/png",
        filename=f"KaushalyaAI_Certificate_{qr_hash[:8]}.png"
    )


@router.get("/verify/{qr_hash}")
def verify_certificate(qr_hash: str, db: Session = Depends(get_db)):
    cert = db.query(models.Certificate).filter(
        models.Certificate.qr_hash == qr_hash
    ).first()
    if not cert:
        return {"valid": False, "message": "Certificate not found"}

    user = db.query(models.User).filter(models.User.id == cert.user_id).first()
    submission = db.query(models.Submission).filter(
        models.Submission.id == cert.submission_id
    ).first()
    assessment = db.query(models.Assessment).filter(
        models.Assessment.id == (submission.assessment_id if submission else 0)
    ).first()

    return {
        "valid": cert.is_valid,
        "holder_name": user.name if user else "Unknown",
        "assessment_title": assessment.title if assessment else "Unknown",
        "score": submission.total_score if submission else 0,
        "issued_at": cert.issued_at,
        "platform": "KaushalyaAI — AI Skill Assessment Platform"
    }


@router.get("/mine")
def my_certificates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    certs = db.query(models.Certificate).filter(
        models.Certificate.user_id == current_user.id,
        models.Certificate.is_valid == True
    ).order_by(models.Certificate.issued_at.desc()).all()

    result = []
    for c in certs:
        submission = db.query(models.Submission).filter(
            models.Submission.id == c.submission_id
        ).first()
        assessment = db.query(models.Assessment).filter(
            models.Assessment.id == (submission.assessment_id if submission else 0)
        ).first()

        result.append({
            "id": c.id,
            "qr_hash": c.qr_hash,
            "assessment_title": assessment.title if assessment else "Unknown",
            "assessment_emoji": assessment.thumbnail_emoji if assessment else "📚",
            "score": submission.total_score if submission else 0,
            "issued_at": c.issued_at,
            "cert_url": f"{settings.BACKEND_URL}/api/certificates/download/{c.qr_hash}"
        })

    return result
