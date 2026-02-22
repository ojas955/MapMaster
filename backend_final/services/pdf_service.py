import pdfplumber
import os
from typing import Tuple, List
from langdetect import detect, LangDetectException


def extract_text_from_pdf(file_path: str) -> Tuple[str, int, str]:
    """
    Extract text from PDF file.
    Returns: (extracted_text, num_pages, detected_language)
    """
    full_text = []
    num_pages = 0

    try:
        with pdfplumber.open(file_path) as pdf:
            num_pages = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text.strip())
    except Exception as e:
        raise ValueError(f"Failed to extract PDF text: {str(e)}")

    combined = "\n\n".join(full_text)
    
    if not combined.strip():
        raise ValueError("PDF appears to contain no extractable text (may be image-based).")

    # Detect language
    language = "en"
    try:
        detected = detect(combined[:1000])
        if detected in ["hi", "mr", "en"]:
            language = detected
    except LangDetectException:
        language = "en"

    return combined, num_pages, language


def chunk_text(text: str, max_chars: int = 8000) -> list:
    """Split text into chunks for processing."""
    paragraphs = text.split('\n\n')
    chunks = []
    current = ""
    
    for para in paragraphs:
        if len(current) + len(para) < max_chars:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n\n"
    
    if current:
        chunks.append(current.strip())
    
    return chunks


def get_representative_chunk(text: str, max_chars: int = 15000) -> str:
    """
    Get a comprehensive chunk of text for question generation.
    Takes beginning (intro/definitions) + middle (core content) + end (conclusions/summaries).
    """
    if len(text) <= max_chars:
        return text
    
    # Allocate: 30% from start, 45% from middle, 25% from end
    start_chars = int(max_chars * 0.30)
    mid_chars = int(max_chars * 0.45)
    end_chars = max_chars - start_chars - mid_chars
    
    start_text = text[:start_chars]
    
    mid_point = len(text) // 2
    mid_start = max(start_chars, mid_point - mid_chars // 2)
    mid_text = text[mid_start:mid_start + mid_chars]
    
    end_text = text[-end_chars:]
    
    return f"{start_text}\n\n[...]\n\n{mid_text}\n\n[...]\n\n{end_text}"


def extract_key_terms(text: str, top_n: int = 20) -> List[str]:
    """Extract the most frequent meaningful terms from the text for topic hinting."""
    import re
    from collections import Counter
    
    # Common stopwords
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
        'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'out', 'off', 'over',
        'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
        'where', 'why', 'how', 'all', 'both', 'each', 'few', 'more', 'most',
        'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
        'so', 'than', 'too', 'very', 'just', 'because', 'but', 'and', 'or',
        'if', 'while', 'about', 'up', 'down', 'that', 'this', 'these', 'those',
        'it', 'its', 'i', 'we', 'you', 'he', 'she', 'they', 'them', 'their',
        'which', 'what', 'who', 'whom', 'whose', 'also', 'one', 'two', 'figure',
        'page', 'chapter', 'section', 'example', 'table', 'given', 'using',
    }
    
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in stopwords]
    counts = Counter(filtered)
    
    return [word for word, _ in counts.most_common(top_n)]
