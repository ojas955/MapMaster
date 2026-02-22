import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
import models
import schemas
from auth import get_current_user
from database import get_db
from services.pdf_service import extract_text_from_pdf, get_representative_chunk, extract_key_terms
from services.ai_service import generate_questions_from_text
from config import settings

router = APIRouter(prefix="/api/pdf", tags=["PDF"])

ALLOWED_TYPES = {"application/pdf", "application/x-pdf"}


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    difficulty: str = Form("intermediate"),
    num_questions: int = Form(7),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Save file
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_filename = f"{uuid.uuid4()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    content = await file.read()
    if len(content) > settings.MAX_PDF_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"PDF exceeds {settings.MAX_PDF_SIZE_MB}MB limit")

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Extract text
    try:
        extracted_text, num_pages, detected_lang = extract_text_from_pdf(file_path)
    except ValueError as e:
        os.remove(file_path)
        raise HTTPException(status_code=422, detail=str(e))

    # Use detected language if auto
    final_language = detected_lang if language == "auto" else language

    # Save PDF record
    file_size_kb = len(content) / 1024
    pdf_record = models.PDF(
        uploader_id=current_user.id,
        filename=safe_filename,
        original_filename=file.filename,
        extracted_text=extracted_text,
        num_pages=num_pages,
        language=final_language,
        file_size_kb=round(file_size_kb, 2)
    )
    db.add(pdf_record)
    db.commit()
    db.refresh(pdf_record)

    # Extract key terms for topic hints
    key_terms = extract_key_terms(extracted_text)

    # Generate questions via AI (with topic context)
    text_for_questions = get_representative_chunk(extracted_text)
    questions = generate_questions_from_text(
        text_for_questions,
        language=final_language,
        num_questions=max(5, min(num_questions, 10)),
        difficulty=difficulty,
        pdf_filename=file.filename,
        key_terms=key_terms
    )

    # Create assessment from PDF
    title = file.filename.replace(".pdf", "").replace("_", " ").replace("-", " ").title()
    assessment = models.Assessment(
        pdf_id=pdf_record.id,
        title=f"{title} -- AI Assessment",
        description=f"Auto-generated higher-order assessment from '{file.filename}'. {num_pages} pages analyzed. Key topics: {', '.join(key_terms[:5])}.",
        questions=questions,
        difficulty=difficulty,
        category="PDF Upload",
        language=final_language,
        created_by=current_user.id,
        tags=["pdf", "ai-generated", difficulty] + key_terms[:3],
        thumbnail_emoji="📄"
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return {
        "pdf": {
            "id": pdf_record.id,
            "original_filename": file.filename,
            "num_pages": num_pages,
            "language": final_language,
            "file_size_kb": file_size_kb,
            "key_terms": key_terms[:10]
        },
        "assessment": {
            "id": assessment.id,
            "title": assessment.title,
            "num_questions": len(questions),
            "difficulty": difficulty,
            "language": final_language
        },
        "message": f"Successfully generated {len(questions)} topic-specific questions from {num_pages} pages!"
    }


@router.get("/list")
def list_pdfs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "admin":
        pdfs = db.query(models.PDF).order_by(models.PDF.upload_date.desc()).all()
    else:
        pdfs = db.query(models.PDF).filter(
            models.PDF.uploader_id == current_user.id
        ).order_by(models.PDF.upload_date.desc()).all()

    return [
        {
            "id": p.id,
            "original_filename": p.original_filename,
            "num_pages": p.num_pages,
            "language": p.language,
            "file_size_kb": p.file_size_kb,
            "upload_date": p.upload_date
        }
        for p in pdfs
    ]
