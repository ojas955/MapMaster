import os
from typing import Optional


def transcribe_audio(file_path: str, language: Optional[str] = None) -> dict:
    """
    Transcribe audio/video file using local Whisper (optional).
    Returns: {text, language, duration_seconds}
    """
    try:
        import whisper
        model = whisper.load_model("base")
        options = {}
        if language and language != "en":
            options["language"] = language
        result = model.transcribe(file_path, **options)
        return {
            "text": result.get("text", "").strip(),
            "language": result.get("language", "en"),
            "duration_seconds": 0
        }
    except ImportError:
        return {
            "text": "[Audio transcription unavailable — install openai-whisper with: pip install openai-whisper]",
            "language": language or "en",
            "duration_seconds": 0
        }
    except Exception as e:
        return {
            "text": f"[Transcription error: {str(e)}]",
            "language": language or "en",
            "duration_seconds": 0
        }
