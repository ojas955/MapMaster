from google import genai
import json
import re
from typing import List, Dict, Any, Optional
from config import settings

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi"
}


def get_client():
    if not settings.GEMINI_API_KEY:
        return None
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _generate(prompt: str) -> Optional[str]:
    """Call Gemini and return text response."""
    client = get_client()
    if not client:
        return None
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  QUESTION GENERATION (Fix 1: topic-specific, min 5, uses key terms)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_questions_from_text(
    text: str,
    language: str = "en",
    num_questions: int = 7,
    difficulty: str = "intermediate",
    pdf_filename: str = "",
    key_terms: List[str] = None
) -> List[Dict[str, Any]]:
    """Generate higher-order thinking questions from PDF text using Gemini."""
    lang_name = LANGUAGE_NAMES.get(language, "English")
    num_questions = max(5, num_questions)  # Enforce minimum 5

    # Build topic hint from filename
    topic_hint = ""
    if pdf_filename:
        clean_name = pdf_filename.replace(".pdf", "").replace("_", " ").replace("-", " ")
        topic_hint = f"\nTOPIC HINT (from filename): {clean_name}"

    # Build key terms hint
    terms_hint = ""
    if key_terms:
        terms_hint = f"\nKEY TERMS found in this document (USE THESE in your questions): {', '.join(key_terms[:15])}"

    prompt = f"""You are an expert educator. You have been given text from a specific document. 
Your job is to create assessment questions that are DIRECTLY and SPECIFICALLY about the content in this document.

CRITICAL RULES:
1. Every question MUST reference specific concepts, terms, formulas, or examples FROM THE TEXT BELOW
2. Do NOT create generic questions. If the text is about gravitation, questions must mention gravity, gravitational force, orbits, G constant, etc.
3. Questions must test higher-order thinking (Bloom's: Apply, Analyze, Evaluate, Create)
4. Each question MUST use at least one specific term or concept from the document
5. Generate EXACTLY {num_questions} questions — no fewer
{topic_hint}
{terms_hint}

TEXT FROM DOCUMENT:
{text[:15000]}

REQUIREMENTS:
- Difficulty: {difficulty}
- Language: {lang_name}
- Types: open_ended (essay-style), scenario (real-world application), explanation (explain WHY), whiteboard_capture (draw/write on paper for diagrams, flowcharts, commands, or steps)
- Each question should reference a SPECIFIC section, formula, concept, or example from the text
- If the document naturally involves process flows, architectures, command sequences, or step-by-step procedures, you MAY use type "whiteboard_capture"

Respond ONLY with a valid JSON array:
[
  {{
    "id": 1,
    "text": "A specific question referencing concepts from the text in {lang_name}",
    "type": "open_ended",
    "bloom_level": "analyze",
    "section_reference": "Specific section/concept from the text this relates to",
    "max_score": 10,
    "rubric": {{
      "depth": "What depth is expected",
      "accuracy": "What accuracy criteria",
      "application": "How application is assessed",
      "originality": "What original thinking is expected"
    }}
  }}
]

Bloom levels to use: apply, analyze, evaluate, create
IMPORTANT: Every question text MUST contain at least one specific term from the document."""

    raw = _generate(prompt)
    if raw:
        try:
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group())
                if len(questions) >= 3:  # Accept if at least 3 came back
                    return questions
        except Exception as e:
            print(f"Question parse error: {e}")

    # Retry once with simpler prompt if first attempt failed
    retry_prompt = f"""Generate exactly {num_questions} assessment questions based on this text. 
Questions MUST reference specific content from the text.
{topic_hint}

TEXT: {text[:10000]}

Return ONLY a JSON array where each item has: id, text, type, bloom_level, section_reference, max_score (10), rubric (dict with depth, accuracy, application, originality).
"""
    raw2 = _generate(retry_prompt)
    if raw2:
        try:
            json_match = re.search(r'\[.*\]', raw2, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group())
                if questions:
                    return questions
        except Exception:
            pass

    return get_fallback_questions(language)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EVALUATION (Fix 3: penalize AI-generated, Fix 7: confidence scoring)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def evaluate_submission(
    questions: List[Dict],
    answers: Dict[str, str],
    pdf_text: str = "",
    language: str = "en"
) -> tuple:
    """Evaluate student answers. Returns: (scores_dict, feedback_dict, total_score)"""
    lang_name = LANGUAGE_NAMES.get(language, "English")

    qa_pairs = []
    for i, q in enumerate(questions):
        answer = answers.get(str(i), answers.get(str(q.get("id", i)), "No answer provided"))
        qa_pairs.append(f"Q{i+1} [{q.get('bloom_level','analyze')}]: {q['text']}\nStudent Answer: {answer}")

    qa_text = "\n\n".join(qa_pairs)
    context = pdf_text[:4000] if pdf_text else ""

    prompt = f"""You are a strict educational evaluator. Evaluate these student answers with HIGH STANDARDS.

SOURCE MATERIAL CONTEXT:
{context}

STUDENT RESPONSES ({lang_name}):
{qa_text}

EVALUATION CRITERIA (each 0-10):
1. depth - How thorough and deep is the thinking? (1-3 = shallow/surface-level, 4-6 = moderate, 7-10 = deep analysis)
2. accuracy - Is the content factually correct against the source material? (1-3 = significant errors, 4-6 = partially correct, 7-10 = accurate)
3. application - Does the student apply concepts to real scenarios? (1-3 = no application, 4-6 = basic, 7-10 = strong practical application)
4. originality - Is this the student's OWN thinking or does it read like AI/ChatGPT output?

CRITICAL ORIGINALITY RULES:
- If an answer is overly polished, uses generic academic phrasing, or reads like it was generated by ChatGPT/AI, give originality 1-3
- Signs of AI-generated text: perfect grammar, formulaic structure like "In conclusion", "Furthermore", "It is important to note", generic examples, no personal voice
- Signs of genuine student work: personal examples, informal language, specific references to class/textbook, occasional grammar mistakes, unique perspective
- A copy-pasted answer should get originality 0-2
- Only give originality 7+ if the answer shows genuine personal insight or creative thinking

5. confidence - How confident does the student appear? (1-3 = very uncertain/hedging, 4-6 = moderate, 7-10 = confident and assertive)
- Signs of low confidence: "I think maybe", "I'm not sure but", "probably", excessive hedging
- Signs of high confidence: direct statements, specific claims, assertive language

Respond ONLY with valid JSON:
{{
  "scores": {{
    "0": {{"depth": 5, "accuracy": 6, "application": 4, "originality": 3, "confidence": 5}},
    "1": {{"depth": 7, "accuracy": 8, "application": 6, "originality": 7, "confidence": 8}}
  }},
  "feedback": {{
    "0": "Specific constructive feedback mentioning what was good and what needs improvement",
    "1": "Specific feedback referencing the actual content of their answer"
  }}
}}"""

    raw = _generate(prompt)
    if raw:
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                scores = result.get("scores", {})
                feedback = result.get("feedback", {})
                total = 0
                count = 0
                for idx_scores in scores.values():
                    if isinstance(idx_scores, dict):
                        # Use depth, accuracy, application, originality for total (not confidence)
                        core_scores = [idx_scores.get(k, 5) for k in ["depth", "accuracy", "application", "originality"]]
                        avg = sum(core_scores) / len(core_scores)
                        total += avg
                        count += 1
                total_pct = (total / (count * 10) * 100) if count > 0 else 0
                return scores, feedback, round(total_pct, 1)
        except Exception as e:
            print(f"Evaluation parse error: {e}")

    return get_fallback_evaluation(questions, answers)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AI DETECTION (Fix 3: detect ChatGPT answers via Gemini)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_ai_generated(answers: Dict[str, str]) -> Dict[str, Any]:
    """
    Use Gemini to detect if answers are AI-generated.
    Returns: {question_idx: {ai_probability: 0-100, reason: str}}
    """
    if not answers:
        return {}

    answers_text = "\n\n".join([
        f"Answer {idx}: {text[:500]}" for idx, text in answers.items()
        if text.strip() and len(text.strip()) > 30
    ])

    if not answers_text.strip():
        return {}

    prompt = f"""You are an AI-text detection expert. Analyze these student answers and determine the probability each was generated by AI (like ChatGPT).

ANSWERS TO ANALYZE:
{answers_text}

AI-GENERATED INDICATORS (high probability):
- Perfect grammar and punctuation throughout
- Formulaic academic structure ("In conclusion", "Furthermore", "It is important to note")  
- Generic examples not tied to personal experience
- Overly balanced pros/cons without taking a position
- Sophisticated vocabulary used consistently
- Lack of personal voice or unique perspective
- Cookie-cutter paragraph structure

HUMAN-WRITTEN INDICATORS (low probability):
- Natural conversational tone
- Personal anecdotes or specific examples from experience
- Minor grammatical imperfections
- Unique phrasing or colloquialisms
- Strong opinions or personal stance
- References to specific classes, teachers, or experiences

For each answer, respond with JSON:
{{
  "results": {{
    "0": {{"ai_probability": 85, "reason": "Uses formulaic structure and generic examples"}},
    "1": {{"ai_probability": 20, "reason": "Contains personal examples and informal language"}}
  }}
}}"""

    raw = _generate(prompt)
    if raw:
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("results", {})
        except Exception as e:
            print(f"AI detection parse error: {e}")

    return {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DYNAMIC FOLLOW-UP QUESTIONS (Fix 5)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_followup_question(
    original_question: str,
    student_answer: str,
    pdf_context: str = "",
    language: str = "en"
) -> Optional[Dict[str, Any]]:
    """Generate a follow-up question based on the student's answer."""
    lang_name = LANGUAGE_NAMES.get(language, "English")
    context = pdf_context[:2000] if pdf_context else ""

    prompt = f"""You are an expert educator conducting a Socratic dialogue. A student just answered a question. 
Generate ONE follow-up question that probes deeper into their understanding.

Original Question: {original_question}
Student's Answer: {student_answer[:800]}

Source Material Context:
{context}

FOLLOW-UP RULES:
1. If the answer was VAGUE, ask for a specific example or application
2. If the answer was WRONG, challenge it with "What if [correct scenario]? How would that change your thinking?"
3. If the answer was GOOD, push deeper: "Can you extend this reasoning to [related concept]?"
4. If the answer mentioned a concept, ask them to connect it to another concept from the material
5. Make the follow-up feel like a conversation, not a test

Respond with JSON only:
{{
  "text": "The follow-up question in {lang_name}",
  "type": "followup",
  "probe_reason": "Why this follow-up was chosen (vague/wrong/good/extend)",
  "max_score": 5
}}"""

    raw = _generate(prompt)
    if raw:
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result["bloom_level"] = "evaluate"
                result["id"] = "followup"
                return result
        except Exception as e:
            print(f"Followup parse error: {e}")

    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADAPTIVE PATHWAY (Fix 6: richer, topic-specific, non-repetitive)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_adaptive_pathway(
    scores: Dict[str, Any],
    questions: List[Dict],
    available_topics: List[str],
    assessment_title: str = "",
    weakest_answers: Dict[str, str] = None
) -> Dict[str, Any]:
    """Generate personalized, topic-specific learning pathway."""

    # Build detailed per-question performance breakdown
    perf_details = []
    for q_idx, q_scores in scores.items():
        if isinstance(q_scores, dict) and int(q_idx) < len(questions):
            q = questions[int(q_idx)]
            avg = sum(v for k, v in q_scores.items() if k != "confidence") / max(1, sum(1 for k in q_scores if k != "confidence"))
            weak_criteria = [k for k, v in q_scores.items() if k != "confidence" and v < 5]
            detail = f"- Q{int(q_idx)+1} ({q.get('bloom_level', 'analyze')}): avg {avg:.1f}/10"
            if q.get("section_reference"):
                detail += f" | Topic: {q['section_reference']}"
            if weak_criteria:
                detail += f" | Weak in: {', '.join(weak_criteria)}"
            perf_details.append(detail)

    perf_text = "\n".join(perf_details) if perf_details else "No detailed scores available"

    # Include weakest answer snippets for context
    weak_answer_text = ""
    if weakest_answers:
        snippets = [f"Q{idx}: \"{ans[:150]}...\"" for idx, ans in list(weakest_answers.items())[:3]]
        weak_answer_text = f"\nWeakest answer excerpts:\n" + "\n".join(snippets)

    prompt = f"""A student just completed an assessment titled "{assessment_title}".

DETAILED PERFORMANCE:
{perf_text}
{weak_answer_text}

Available follow-up topics to recommend: {available_topics[:10] if available_topics else ['Review fundamentals', 'Practice problems', 'Advanced applications']}

Based on their SPECIFIC weaknesses, generate a PERSONALIZED learning pathway. 
DO NOT give generic advice like "study more" or "practice regularly".
Instead, give SPECIFIC, ACTIONABLE recommendations tied to this assessment's topic.

Example of BAD (generic): "Focus on improving analytical skills"
Example of GOOD (specific): "Practice deriving the gravitational force equation for non-point masses, then solve problems involving satellite orbital mechanics"

Respond with JSON:
{{
  "skill_gaps": ["Specific gap 1 related to the assessment topic", "Specific gap 2"],
  "recommended_activities": [
    "Specific activity 1 (e.g., 'Solve 5 problems on gravitational potential energy using U = -GMm/r')",
    "Specific activity 2",
    "Specific activity 3"
  ],
  "recommended_topics": ["topic1", "topic2"],
  "reason": "2-3 sentence explanation referencing their specific weak points",
  "next_difficulty": "beginner or intermediate or advanced",
  "focus_bloom_levels": ["analyze", "evaluate"],
  "estimated_study_hours": 3
}}"""

    raw = _generate(prompt)
    if raw:
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"Pathway parse error: {e}")

    # Fallback with at least some useful info
    criteria_totals = {"depth": 0, "accuracy": 0, "application": 0, "originality": 0}
    count = max(1, len(scores))
    for q_scores in scores.values():
        if isinstance(q_scores, dict):
            for k in criteria_totals:
                criteria_totals[k] += q_scores.get(k, 5)

    weak_areas = [k for k, v in criteria_totals.items() if v / count < 6]

    return {
        "skill_gaps": weak_areas or ["Deep Analysis", "Practical Application"],
        "recommended_activities": [
            f"Review core concepts from {assessment_title}" if assessment_title else "Review fundamental concepts",
            "Practice applying theory to real-world problems",
            "Write explanations in your own words without referencing materials"
        ],
        "recommended_topics": available_topics[:3] if available_topics else [],
        "reason": f"Your weakest areas were {', '.join(weak_areas) if weak_areas else 'application and originality'}. Focus on these with targeted practice.",
        "next_difficulty": "intermediate",
        "estimated_study_hours": 3
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIDENCE ANALYSIS (Fix 7)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_confidence(answers: Dict[str, str]) -> Dict[str, float]:
    """
    Analyze text-based confidence signals in student answers.
    Returns: {question_idx: confidence_score 0-100}
    """
    hedging_phrases = [
        "i think", "maybe", "i'm not sure", "perhaps", "possibly", "i guess",
        "i believe", "probably", "might be", "could be", "not certain",
        "i don't know", "something like", "sort of", "kind of", "i suppose"
    ]
    confident_phrases = [
        "clearly", "obviously", "definitely", "certainly", "without doubt",
        "this shows", "this proves", "this demonstrates", "the evidence",
        "therefore", "as we can see", "it is clear", "undoubtedly"
    ]

    results = {}
    for idx, answer in answers.items():
        if not answer or len(answer.strip()) < 10:
            results[idx] = 50.0
            continue

        lower = answer.lower()
        word_count = len(answer.split())

        hedge_count = sum(1 for p in hedging_phrases if p in lower)
        confident_count = sum(1 for p in confident_phrases if p in lower)

        # Base score
        score = 60.0

        # Length factor (very short = less confident)
        if word_count < 20:
            score -= 15
        elif word_count > 80:
            score += 10

        # Hedging penalty
        score -= hedge_count * 8

        # Confidence bonus
        score += confident_count * 6

        # Exclamation marks suggest confidence
        score += min(10, answer.count("!") * 3)

        # Question marks in answer suggest uncertainty
        score -= min(15, answer.count("?") * 5)

        results[idx] = max(0, min(100, round(score)))

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FALLBACKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_fallback_questions(language: str = "en") -> List[Dict]:
    return [
        {
            "id": i + 1,
            "text": text,
            "type": "open_ended",
            "bloom_level": level,
            "section_reference": "Core concepts",
            "max_score": 10,
            "rubric": {"depth": "Thorough analysis", "accuracy": "Factual correctness", "application": "Real-world connection", "originality": "Personal insight"}
        }
        for i, (text, level) in enumerate([
            ("Analyze the main concepts presented and explain how they could be applied to solve a real-world problem.", "apply"),
            ("Compare and contrast two key ideas from the material. What are their strengths and limitations?", "analyze"),
            ("Critically evaluate the methodology or approach described. What would you improve and why?", "evaluate"),
            ("Propose a novel application or extension of the concepts discussed.", "create"),
            ("How would the concepts change if applied in a completely different context? Give a specific example.", "apply"),
        ])
    ]


def get_fallback_evaluation(questions: List[Dict], answers: Dict) -> tuple:
    import random
    scores = {}
    feedback = {}
    total = 0

    for i, q in enumerate(questions):
        answer = answers.get(str(i), "")
        word_count = len(answer.split()) if answer else 0
        base = min(word_count / 8, 7) + random.uniform(0, 2)
        score_val = round(min(base, 9), 1)
        scores[str(i)] = {
            "depth": max(0, min(10, round(score_val + random.uniform(-1, 1), 1))),
            "accuracy": max(0, min(10, round(score_val + random.uniform(-1, 1), 1))),
            "application": max(0, min(10, round(score_val + random.uniform(-1, 1), 1))),
            "originality": max(0, min(10, round(score_val + random.uniform(-2, 0.5), 1))),
            "confidence": max(0, min(10, round(score_val + random.uniform(-1, 1), 1)))
        }
        feedback[str(i)] = "Focus on providing specific examples and deeper analysis. Reference the source material directly."
        total += score_val

    total_pct = (total / (len(questions) * 10) * 100) if questions else 0
    return scores, feedback, round(total_pct, 1)
