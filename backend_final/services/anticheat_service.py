import difflib
import re
from typing import Dict, Any, List


# Common ChatGPT/AI phrasing patterns for n-gram detection
AI_PHRASES = [
    "it is important to note",
    "in conclusion",
    "furthermore",
    "in summary",
    "it is worth mentioning",
    "it should be noted",
    "this highlights the importance",
    "plays a crucial role",
    "it is essential to",
    "in light of",
    "as mentioned earlier",
    "it can be observed that",
    "one must consider",
    "this underscores",
    "in today's world",
    "in the context of",
    "it is evident that",
    "taking into account",
    "from a broader perspective",
    "this serves as a reminder",
    "delving into",
    "navigating the complexities",
    "a testament to",
    "shed light on",
    "foster a deeper understanding",
    "multifaceted approach",
    "holistic understanding",
    "nuanced perspective",
    "leveraging the power of",
    "plays a pivotal role",
]


def check_plagiarism_vs_source(answer: str, source_text: str) -> float:
    """Check if answer is copy-pasted from source PDF text. Returns 0.0 to 1.0."""
    if not answer or not source_text:
        return 0.0

    answer_norm = re.sub(r'\s+', ' ', answer.lower().strip())
    source_norm = re.sub(r'\s+', ' ', source_text.lower().strip())

    if len(answer_norm) > 50:
        words = answer_norm.split()
        window_size = min(20, len(words))
        for i in range(len(words) - window_size + 1):
            window = ' '.join(words[i:i + window_size])
            if window in source_norm:
                return 0.9

    ratio = difflib.SequenceMatcher(None, answer_norm[:2000], source_norm[:5000]).ratio()
    return round(ratio, 3)


def check_answer_originality(answer: str, other_answers: List[str]) -> float:
    """Compare answer against other submissions. Returns 0.0 (copied) to 1.0 (original)."""
    if not other_answers:
        return 1.0

    answer_norm = re.sub(r'\s+', ' ', answer.lower().strip())
    max_similarity = 0.0

    for other in other_answers:
        other_norm = re.sub(r'\s+', ' ', other.lower().strip())
        ratio = difflib.SequenceMatcher(None, answer_norm[:1000], other_norm[:1000]).ratio()
        max_similarity = max(max_similarity, ratio)

    return round(1.0 - max_similarity, 3)


def detect_ai_phrases(answer: str) -> Dict[str, Any]:
    """
    Detect common AI/ChatGPT phrasing patterns using n-gram matching.
    Returns: {ai_phrase_count, ai_phrases_found, ai_phrase_score 0-100}
    """
    if not answer or len(answer.strip()) < 30:
        return {"ai_phrase_count": 0, "ai_phrases_found": [], "ai_phrase_score": 0}

    lower = answer.lower()
    found = [phrase for phrase in AI_PHRASES if phrase in lower]

    word_count = len(answer.split())
    # Normalize: more phrases per word count = more suspicious
    density = (len(found) / max(1, word_count / 50)) * 100

    return {
        "ai_phrase_count": len(found),
        "ai_phrases_found": found[:5],  # Show top 5
        "ai_phrase_score": min(100, round(density))
    }


def analyze_submission(
    answers: Dict[str, str],
    source_text: str = "",
    tab_switches: int = 0,
    copy_paste_count: int = 0,
    previous_submissions_answers: List[Dict] = None,
    ai_detection_results: Dict = None
) -> Dict[str, Any]:
    """Run comprehensive anti-cheat analysis with AI detection."""
    flags = {
        "tab_switches": tab_switches,
        "copy_paste_count": copy_paste_count,
        "plagiarism_scores": {},
        "originality_scores": {},
        "ai_detection": {},
        "overall_integrity_score": 100,
        "risk_level": "low",
        "flags_triggered": []
    }

    integrity_score = 100

    # Tab switch penalties
    if tab_switches > 5:
        integrity_score -= min(30, tab_switches * 3)
        flags["flags_triggered"].append(f"High tab switches: {tab_switches}")
    elif tab_switches > 2:
        integrity_score -= 10
        flags["flags_triggered"].append(f"Moderate tab switches: {tab_switches}")

    # Copy-paste penalties
    if copy_paste_count > 3:
        integrity_score -= min(20, copy_paste_count * 4)
        flags["flags_triggered"].append(f"Copy-paste detected: {copy_paste_count} times")

    # Plagiarism check vs source PDF
    if source_text:
        for q_idx, answer in answers.items():
            if len(answer.strip()) < 20:
                continue
            plagiarism_ratio = check_plagiarism_vs_source(answer, source_text)
            flags["plagiarism_scores"][q_idx] = plagiarism_ratio

            if plagiarism_ratio > 0.7:
                integrity_score -= 25
                flags["flags_triggered"].append(f"High plagiarism on Q{int(q_idx)+1}: {plagiarism_ratio:.0%}")
            elif plagiarism_ratio > 0.4:
                integrity_score -= 10
                flags["flags_triggered"].append(f"Moderate plagiarism on Q{int(q_idx)+1}: {plagiarism_ratio:.0%}")

    # Originality check vs previous submissions
    if previous_submissions_answers:
        for q_idx, answer in answers.items():
            other_answers = [
                sub.get(q_idx, "") for sub in previous_submissions_answers
                if sub.get(q_idx)
            ]
            orig_score = check_answer_originality(answer, other_answers)
            flags["originality_scores"][q_idx] = orig_score

            if orig_score < 0.3:
                integrity_score -= 15
                flags["flags_triggered"].append(f"Low originality on Q{int(q_idx)+1}")

    # AI phrase detection (local, fast)
    for q_idx, answer in answers.items():
        if len(answer.strip()) < 30:
            continue
        ai_local = detect_ai_phrases(answer)
        if ai_local["ai_phrase_count"] >= 3:
            integrity_score -= min(20, ai_local["ai_phrase_count"] * 5)
            flags["flags_triggered"].append(
                f"AI-like phrasing on Q{int(q_idx)+1}: {ai_local['ai_phrase_count']} patterns detected"
            )
        flags["ai_detection"][q_idx] = ai_local

    # Gemini-based AI detection results (if available)
    if ai_detection_results:
        for q_idx, result in ai_detection_results.items():
            if isinstance(result, dict):
                prob = result.get("ai_probability", 0)
                reason = result.get("reason", "")
                if q_idx in flags["ai_detection"]:
                    flags["ai_detection"][q_idx]["gemini_ai_probability"] = prob
                    flags["ai_detection"][q_idx]["gemini_reason"] = reason
                else:
                    flags["ai_detection"][q_idx] = {"gemini_ai_probability": prob, "gemini_reason": reason}

                if prob >= 80:
                    integrity_score -= 20
                    flags["flags_triggered"].append(
                        f"AI-generated content suspected on Q{int(q_idx)+1} ({prob}%): {reason}"
                    )
                elif prob >= 60:
                    integrity_score -= 10
                    flags["flags_triggered"].append(
                        f"Possibly AI-assisted on Q{int(q_idx)+1} ({prob}%)"
                    )

    # Final scoring
    integrity_score = max(0, integrity_score)
    flags["overall_integrity_score"] = integrity_score

    if integrity_score >= 80:
        flags["risk_level"] = "low"
    elif integrity_score >= 50:
        flags["risk_level"] = "medium"
    else:
        flags["risk_level"] = "high"

    return flags
