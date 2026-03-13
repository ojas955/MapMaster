import json
import mimetypes
import os
import re
from typing import Any, Dict, Tuple

from google.genai import types

import models
from config import settings
from database import SessionLocal
from services.ai_service import LANGUAGE_NAMES, get_client

CAPTURE_TYPE_HINTS = {
    "whiteboard",
    "whiteboard_capture",
    "diagram",
    "diagram_capture",
    "flowchart",
    "commands",
    "steps",
    "capture",
    "visual",
}

CAPTURE_PATTERN = re.compile(
    r"(draw|diagram|flow\s?chart|figure|sketch|illustrate|white\s?paper|whiteboard|write the steps|write steps|commands?|command sequence|workflow|architecture|block diagram|process flow)",
    re.IGNORECASE,
)

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "using", "write", "draw", "create",
    "show", "then", "what", "when", "where", "which", "have", "will", "about", "their", "there", "should",
    "would", "could", "explain", "question", "response", "answer", "paper", "whiteboard", "flow", "diagram",
}


def question_requires_visual_capture(question: Dict[str, Any]) -> Tuple[bool, str]:
    q_type = (question.get("type") or "").strip().lower()
    if q_type in CAPTURE_TYPE_HINTS:
        return True, q_type

    text = (question.get("text") or "").strip()
    if CAPTURE_PATTERN.search(text):
        if re.search(r"commands?|command sequence", text, re.IGNORECASE):
            return True, "commands"
        if re.search(r"steps?|workflow|process flow", text, re.IGNORECASE):
            return True, "steps"
        return True, "diagram"

    return False, "text"


def enrich_question_for_capture(question: Dict[str, Any]) -> Dict[str, Any]:
    capture_required, capture_mode = question_requires_visual_capture(question)
    enriched = dict(question)
    enriched["capture_required"] = capture_required
    enriched["capture_mode"] = capture_mode
    if capture_required:
        enriched["capture_hint"] = (
            "Use Capture to photograph your handwritten white-paper response. "
            "You can also add a short typed note if needed."
        )
    return enriched


def _parse_json_object(raw_text: str) -> Dict[str, Any]:
    if not raw_text:
        return {}

    try:
        return json.loads(raw_text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return {}

    try:
        return json.loads(match.group())
    except Exception:
        return {}


def _score_average(scores: Dict[str, Any]) -> float:
    if not isinstance(scores, dict):
        return 0.0
    core = [float(scores.get(k, 0) or 0) for k in ["depth", "accuracy", "application", "originality"]]
    return round(sum(core) / max(1, len(core)), 1)


def _extract_keywords(question_text: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", (question_text or "").lower())
        if token not in STOPWORDS
    ]


def _fallback_visual_evaluation(question: Dict[str, Any], typed_context: str = "") -> Dict[str, Any]:
    question_text = question.get("text", "")
    keywords = _extract_keywords(question_text)
    note_text = (typed_context or "").strip()
    note_lower = note_text.lower()
    overlap = sum(1 for keyword in keywords[:10] if keyword in note_lower)
    coverage = overlap / max(1, min(len(keywords), 10))

    base = 2.5 + (coverage * 5.5)
    if len(note_text.split()) > 12:
        base += 0.8

    base = max(1.5, min(8.5, base))
    scores = {
        "depth": round(min(10, base), 1),
        "accuracy": round(min(10, base + 0.4), 1),
        "application": round(min(10, base - 0.2), 1),
        "originality": round(min(10, base + 0.2), 1),
    }

    if note_text:
        summary = note_text[:500]
        feedback = (
            "Capture saved. A typed note was used as fallback context because multimodal evaluation is not available right now. "
            "Add a GEMINI_API_KEY for full automatic diagram and handwritten-answer analysis."
        )
    else:
        summary = "Handwritten answer image captured successfully."
        feedback = (
            "Capture saved, but automatic interpretation is limited without Gemini multimodal access. "
            "Set GEMINI_API_KEY for best results on diagrams, commands, and handwritten steps."
        )

    return {
        "transcribed_text": note_text,
        "summary": summary,
        "matches_question": coverage >= 0.35 if note_text else False,
        "scores": scores,
        "feedback": feedback,
        "strengths": ["Response image captured successfully"],
        "gaps": ["Automatic visual understanding is running in fallback mode"],
        "legibility": 60 if note_text else 35,
        "overall_score": _score_average(scores),
        "evaluator_used": "fallback",
    }


def evaluate_visual_capture_payload(
    question: Dict[str, Any],
    image_path: str,
    language: str = "en",
    typed_context: str = "",
) -> Dict[str, Any]:
    client = get_client()
    if not client:
        return _fallback_visual_evaluation(question, typed_context)

    mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    lang_name = LANGUAGE_NAMES.get(language, "English")
    prompt = f"""You are evaluating a student's handwritten white-paper interview answer.

QUESTION:
{question.get('text', '')}

QUESTION TYPE:
{question.get('type', 'whiteboard')}

BLOOM LEVEL:
{question.get('bloom_level', 'analyze')}

RUBRIC:
{json.dumps(question.get('rubric', {}), ensure_ascii=False)}

OPTIONAL TYPED NOTE FROM STUDENT:
{typed_context or 'None'}

TASK:
1. Read the handwritten text, commands, labels, arrows, and diagram structure from the image.
2. Infer what the student is trying to answer even if handwriting is imperfect.
3. Judge whether the response correctly addresses the question.
4. Be strict but fair.

Respond ONLY as valid JSON with this exact structure:
{{
  "transcribed_text": "string",
  "summary": "2-4 sentence summary of what is on the page",
  "matches_question": true,
  "scores": {{
    "depth": 0,
    "accuracy": 0,
    "application": 0,
    "originality": 0
  }},
  "feedback": "clear constructive feedback",
  "strengths": ["item 1", "item 2"],
  "gaps": ["item 1", "item 2"],
  "legibility": 0
}}

Use {lang_name} in the feedback."""

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
        )
        parsed = _parse_json_object(getattr(response, "text", "") or "")
        if parsed:
            scores = parsed.get("scores", {}) or {}
            parsed["overall_score"] = _score_average(scores)
            parsed["evaluator_used"] = "gemini-multimodal"
            return parsed
    except Exception as exc:
        print(f"Visual capture evaluation failed: {exc}")

    return _fallback_visual_evaluation(question, typed_context)


def evaluate_capture_record(db, capture: models.VisualCapture, assessment: models.Assessment, question: Dict[str, Any]):
    try:
        capture.status = "processing"
        db.commit()

        result = evaluate_visual_capture_payload(
            question=question,
            image_path=capture.image_path,
            language=assessment.language,
            typed_context=capture.typed_context or "",
        )

        capture.status = "completed"
        capture.extracted_text = result.get("transcribed_text", "")
        capture.analysis_summary = result.get("summary", "")
        capture.scores = result.get("scores", {})
        capture.feedback = result.get("feedback", "")
        capture.overall_score = result.get("overall_score", 0.0)
        capture.evaluator_used = result.get("evaluator_used", "fallback")
        db.commit()
        db.refresh(capture)
        return capture
    except Exception as exc:
        db.rollback()
        capture.status = "failed"
        capture.feedback = f"Automatic evaluation failed: {exc}"
        capture.evaluator_used = "error"
        db.add(capture)
        db.commit()
        db.refresh(capture)
        return capture


def process_visual_capture(capture_id: int):
    db = SessionLocal()
    try:
        capture = db.query(models.VisualCapture).filter(models.VisualCapture.id == capture_id).first()
        if not capture:
            return

        assessment = db.query(models.Assessment).filter(models.Assessment.id == capture.assessment_id).first()
        if not assessment:
            capture.status = "failed"
            capture.feedback = "Assessment not found for this capture."
            db.commit()
            return

        questions = assessment.questions or []
        if capture.question_index < 0 or capture.question_index >= len(questions):
            capture.status = "failed"
            capture.feedback = "Question not found for this capture."
            db.commit()
            return

        evaluate_capture_record(db, capture, assessment, questions[capture.question_index])
    finally:
        db.close()
