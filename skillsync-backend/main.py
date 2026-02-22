from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import requests
import os
from dotenv import load_dotenv
import subprocess
import tempfile
import sys
from google import genai
from google.genai import types
import json
import ast
import hashlib
import re
import fitz  # PyMuPDF for PDF parsing
from bs4 import BeautifulSoup
from originality_engine import analyze_originality, analyze_batch_originality

# Load environment variables (API keys) from .env file
load_dotenv()

app = FastAPI(title="OmniParse AI - Intelligent Document Processing Engine")

# ============================================================
# JSON SANITIZATION HELPER
# ============================================================
def safe_json_loads(raw_text: str) -> dict:
    """
    Robustly parse JSON from Gemini API responses that may contain:
    1. Invalid control characters inside strings (literal newlines, tabs)
    2. Invalid backslash escape sequences (\\<space>, \\p, \\| etc.)
    3. ASCII art tree diagrams with / \\ | characters that break JSON escaping

    Uses a multi-pass strategy: try strict first, then progressively fix issues.
    """
    # --- Pass 1: Try parsing as-is (works if Gemini returned clean JSON) ---
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # --- Pass 2: Try with strict=False (allows control chars inside strings) ---
    try:
        return json.loads(raw_text, strict=False)
    except json.JSONDecodeError:
        pass

    # --- Pass 3: Fix invalid backslash escapes, then parse with strict=False ---
    # In JSON, only these escape sequences are valid: \" \\ \/ \b \f \n \r \t \uXXXX
    # Gemini often produces \<space>, \|, \., \( etc. from ASCII art / code.
    # Fix by doubling the backslash so \<invalid> becomes \\<invalid> (literal backslash + char).
    fixed = re.sub(
        r'\\(?!["\\/bfnrtu])',   # backslash NOT followed by a valid escape char
        r'\\\\',                  # replace with double-backslash
        raw_text
    )
    try:
        return json.loads(fixed, strict=False)
    except json.JSONDecodeError:
        pass

    # --- Pass 4: Strip control chars + fix escapes ---
    stripped = re.sub(r'[\x00-\x1f\x7f]', ' ', raw_text)
    fixed2 = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', stripped)
    try:
        return json.loads(fixed2, strict=False)
    except json.JSONDecodeError:
        pass

    # --- Pass 5: Nuclear — iteratively fix until parseable ---
    # Some Gemini responses have layered escape issues where a single regex pass
    # creates new invalid sequences. Loop until stable or parseable.
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', raw_text)
    for _ in range(5):
        text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            pass

    # --- Pass 6: Last resort — strip ALL backslashes that aren't part of \\n, \\t, \\", \\\\ ---
    # This loses some formatting but guarantees parseable JSON.
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', raw_text)
    # First, protect valid 2-char escape sequences by replacing with placeholders
    text = text.replace('\\\\', '\x00DBLBACK\x00')
    text = text.replace('\\"', '\x00DBLQUOT\x00')
    text = text.replace('\\n', '\x00NEWLINE\x00')
    text = text.replace('\\t', '\x00TAB\x00')
    text = text.replace('\\r', '\x00CR\x00')
    text = text.replace('\\b', '\x00BS\x00')
    text = text.replace('\\f', '\x00FF\x00')
    text = text.replace('\\/', '\x00FSLASH\x00')
    # Now any remaining backslash is invalid — remove it
    text = text.replace('\\', '')
    # Restore valid sequences
    text = text.replace('\x00DBLBACK\x00', '\\\\')
    text = text.replace('\x00DBLQUOT\x00', '\\"')
    text = text.replace('\x00NEWLINE\x00', '\\n')
    text = text.replace('\x00TAB\x00', '\\t')
    text = text.replace('\x00CR\x00', '\\r')
    text = text.replace('\x00BS\x00', '\\b')
    text = text.replace('\x00FF\x00', '\\f')
    text = text.replace('\x00FSLASH\x00', '\\/')
    # Also handle \uXXXX sequences that were stripped
    # (rare edge case, acceptable loss)
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError as e:
        print(f"[safe_json_loads] ALL 6 PASSES FAILED. Final error: {e}")
        print(f"[safe_json_loads] Raw text (first 500 chars): {repr(raw_text[:500])}")
        # Re-raise with clear context so callers can handle it
        raise

# ============================================================
# IN-MEMORY CACHE FOR PRODUCTION SPEED
# ============================================================
# Cache stores generated scenarios to avoid redundant Gemini API calls
# Key: URL string or hash of PDF content | Value: Generated JSON response
SCENARIO_CACHE: Dict[str, dict] = {}

def get_cache_key_for_text(text: str) -> str:
    """Generate a cache key by hashing the first 2000 characters of text."""
    text_sample = text[:2000]
    return hashlib.sha256(text_sample.encode('utf-8')).hexdigest()

def get_cached_response(cache_key: str) -> Optional[dict]:
    """Check if a cached response exists for the given key."""
    if cache_key in SCENARIO_CACHE:
        print(f"[CACHE HIT]: Returning cached response for key {cache_key[:16]}...")
        return SCENARIO_CACHE[cache_key]
    print(f"[CACHE MISS]: No cached response for key {cache_key[:16]}...")
    return None

def cache_response(cache_key: str, response: dict) -> None:
    """Store a response in the cache."""
    SCENARIO_CACHE[cache_key] = response
    print(f"[CACHED]: Stored response for key {cache_key[:16]}... (Total cached: {len(SCENARIO_CACHE)})")

# Crucial: Allow React to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data Models ---
class RunPayload(BaseModel):
    code: str
    sample_tests: Optional[str] = None        # 3 basic sample test cases (for "Run Code")
    comprehensive_tests: Optional[str] = None  # 50+ edge cases (for "Submit")
    is_submit: bool = False                    # False = Run Code, True = Submit

class LogEntry(BaseModel):
    attempt: int
    log: str

class SubmissionPayload(BaseModel):
    code: str
    attempts: int
    logs: List[LogEntry]
    tab_switches: int = 0    # How many times user switched tabs (anti-cheat)
    paste_count: int = 0     # How many times user pasted code (anti-cheat)
    proctoring_data: Optional[Dict[str, Any]] = None  # AI proctor stats
    time_taken_seconds: int = 0

class URLPayload(BaseModel):
    url: str

class BatchEvalQuestion(BaseModel):
    """A single question's telemetry for batch AI evaluation."""
    question_type: str
    title: str
    code: str
    attempts: int
    logs: List[LogEntry] = []

class BatchEvalPayload(BaseModel):
    """Payload from React when evaluating all 4 questions at once."""
    questions: List[BatchEvalQuestion]
    tab_switches: int = 0    # How many times user switched tabs (anti-cheat)
    paste_count: int = 0     # How many times user pasted code (anti-cheat)
    proctoring_data: Optional[Dict[str, Any]] = None  # AI proctor stats
    time_taken_seconds: int = 0


class BatchQuestion(BaseModel):
    """Schema for a single question in a batch assessment."""
    question_type: str  # "scratch" | "logic_bug" | "syntax_error" | "optimization"
    title: str
    description: str
    difficulty: str  # "Easy" | "Medium" | "Hard"
    time_limit_minutes: int
    user_code: str
    sample_tests: str
    comprehensive_tests: str
    hints: List[str]
    tags: List[str]


class BatchAssessmentResult(BaseModel):
    """Schema for the complete batch assessment response."""
    topic: str
    total_questions: int
    estimated_time_minutes: int
    questions: List[BatchQuestion]

class AnalysisResult(BaseModel):
    category: str
    confidence: str
    summary: str
    key_metrics: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]
    user_code: Optional[str] = None           # Code shown in editor (no answers)
    sample_tests: Optional[str] = None        # 3 sample tests for "Run Code"
    comprehensive_tests: Optional[str] = None  # 50+ tests for "Submit"


# --- STATIC ANALYSIS UTILITY ---
def analyze_code_ast(code_string: str):
    """
    Deterministically analyzes code complexity and security vulnerabilities.
    """
    metrics = {
        "cyclomatic_complexity": 1, # Base complexity is 1
        "has_security_vulnerability": False,
        "function_count": 0,
        "variable_names": []
    }

    try:
        tree = ast.parse(code_string)

        # Walk through every node in the syntax tree
        for node in ast.walk(tree):
            # 1. Calculate Cyclomatic Complexity (count decision points)
            if isinstance(node, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.ExceptHandler)):
                metrics["cyclomatic_complexity"] += 1

            # 2. Check for Security Vulnerabilities (e.g., using eval or exec)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec', 'system']:
                    metrics["has_security_vulnerability"] = True

            # 3. Count Functions
            elif isinstance(node, ast.FunctionDef):
                metrics["function_count"] += 1

            # 4. Extract Variable Names (to check if they use 'x' instead of 'user_id')
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id not in metrics["variable_names"]:
                    metrics["variable_names"].append(node.id)

        return metrics

    except SyntaxError:
        # If the code is completely broken, the AST can't build the tree
        return {"error": "SyntaxError: Code could not be parsed statically."}


# ============================================================
# SYNTAX AUTO-FIXER FOR LLM-GENERATED TEST SCRIPTS
# ============================================================
def _fix_syntax_errors(code: str) -> str:
    """
    Pre-flight check: compile the stitched code and if there's a SyntaxError
    caused by mismatched brackets (from LLM-generated nested tree literals),
    comment out the broken line(s) so the rest of the script can still run.

    This is a safety net — it doesn't change prompts or strip functions.
    It just prevents bracket typos from crashing the entire test suite.
    """
    max_fixes = 10  # Safety limit to avoid infinite loops
    for attempt in range(max_fixes):
        try:
            compile(code, "<test>", "exec")
            return code  # No syntax errors — return as-is
        except SyntaxError as e:
            if e.lineno is None:
                return code  # Can't determine line — give up

            lines = code.split('\n')
            bad_line_idx = e.lineno - 1  # Convert to 0-based

            if bad_line_idx < 0 or bad_line_idx >= len(lines):
                return code  # Out of range — give up

            bad_line = lines[bad_line_idx]

            # Only auto-fix if the line looks like a broken tree/list literal
            # (contains nested brackets). Don't touch user's actual code.
            bracket_count = bad_line.count('[') + bad_line.count(']')
            if bracket_count >= 3:
                print(f"[SYNTAX FIX] Commenting out broken tree literal at line {e.lineno}: {bad_line.strip()[:80]}...")
                lines[bad_line_idx] = f"# [AUTO-FIXED] Removed broken nested literal: {bad_line.strip()[:60]}"

                # Also check the line above — sometimes the opening ( is on the previous line
                # and the broken literal continues, or the line is a continuation
                if bad_line_idx > 0:
                    prev_line = lines[bad_line_idx - 1].strip()
                    # If previous line ends with an opening bracket or comma and has nested brackets
                    if prev_line and (prev_line.endswith(',') or prev_line.endswith('(') or prev_line.endswith('[')):
                        prev_bracket_count = prev_line.count('[') + prev_line.count(']')
                        if prev_bracket_count >= 3:
                            print(f"[SYNTAX FIX] Also fixing continuation line {e.lineno - 1}: {prev_line[:80]}...")
                            lines[bad_line_idx - 1] = f"# [AUTO-FIXED] {prev_line[:60]}"

                code = '\n'.join(lines)
            else:
                # Not a bracket issue — this is a real syntax error, don't touch it
                return code

    return code  # Exhausted fix attempts


def _strip_solution_class_from_tests(test_code: str) -> str:
    """
    Remove any `class Solution:` block (and its indented body) from test scripts.

    The LLM sometimes includes a dummy Solution class in sample_tests or
    comprehensive_tests. When the test script is stitched after the user's code,
    this dummy class OVERRIDES the user's real Solution class, causing every
    method to return None.

    This regex removes the class definition and all its indented body lines,
    while preserving everything else (imports, helpers, if __name__ block, etc.).
    """
    if not test_code or 'class Solution' not in test_code:
        return test_code  # Fast path: nothing to strip

    # Match `class Solution(...):` followed by all indented lines belonging to it.
    # The pattern captures:
    #   - The class line itself (with optional inheritance like `class Solution(object):`)
    #   - All subsequent lines that are either indented (part of the class body)
    #     or blank (empty lines within the class)
    # It stops when it hits a non-indented, non-blank line (like `if __name__`).
    pattern = re.compile(
        r'^class\s+Solution\b[^\n]*:\s*\n'  # class Solution...: line
        r'(?:[ \t]+[^\n]*\n|\s*\n)*',        # indented body lines + blank lines
        re.MULTILINE
    )

    cleaned = pattern.sub('', test_code)

    if cleaned != test_code:
        print("[SANITIZE] Stripped duplicate 'class Solution' from test script")

    return cleaned


# ─── IMPORT SANITIZER ────────────────────────────────────────────────────────
# Ensures that generated code always contains necessary imports.
# The LLM sometimes forgets `from typing import ...` despite explicit prompts.
IMPORT_HEADER = "import math\nimport heapq\nfrom typing import List, Optional, Dict, Set, Tuple, Any\nfrom collections import defaultdict, deque, Counter\nfrom functools import lru_cache\n"
TEST_IMPORT_HEADER = "import sys\nimport math\nimport heapq\nfrom typing import List, Optional, Dict, Set, Tuple, Any\nfrom collections import defaultdict, deque, Counter\nfrom functools import lru_cache\n"

def _fix_code_escaping(code: str) -> str:
    """
    Fix double-escaped newlines in code strings from Gemini JSON responses.
    
    Gemini sometimes outputs \\n (double-escaped) in JSON strings instead of \n.
    After json.loads, these become literal backslash+n (2 chars) instead of
    actual newline characters, causing Python SyntaxErrors like:
      'unexpected character after line continuation character'
    
    Detection: If code has very few actual newlines relative to its length,
    it's almost certainly a double-escaping issue.
    """
    if not code or not isinstance(code, str):
        return code
    
    # Strip any leading/trailing whitespace and BOM
    code = code.strip().lstrip('\ufeff')
    
    actual_newlines = code.count('\n')
    literal_backslash_n = code.count('\\n')
    
    # If code has literal \n sequences and very few actual newlines, fix it
    if literal_backslash_n > 2 and actual_newlines < literal_backslash_n:
        code = code.replace('\\n', '\n')
        code = code.replace('\\t', '\t')
        code = code.replace('\\r', '')
        code = code.replace('\\"', '"')
        code = code.replace("\\'", "'")
    
    # Also handle triple-escaped sequences (\\\n -> \n)
    if '\\\\n' in code:
        code = code.replace('\\\\n', '\n')
        code = code.replace('\\\\t', '\t')
    
    # Fix Windows-style line endings
    code = code.replace('\r\n', '\n').replace('\r', '\n')
    
    return code

def _ensure_imports_in_code(code: str, is_test: bool = False) -> str:
    """Ensure code starts with standard typing imports. Idempotent."""
    if not code or not isinstance(code, str):
        return code
    # First fix any double-escaped newlines
    code = _fix_code_escaping(code)
    header = TEST_IMPORT_HEADER if is_test else IMPORT_HEADER
    # Skip if already has a typing import line
    if "from typing import" in code:
        return code
    return header + code

def _ensure_node_class_in_tests(user_code: str, test_code: str) -> str:
    """
    If user_code defines a Node/TreeNode/ListNode class, ensure the test script
    also re-defines it (since tests are stitched after user_code, they need it).
    Only adds if not already present in the test code.
    """
    if not user_code or not test_code:
        return test_code
    # Check what custom classes the user_code defines
    import re as _re
    defined_classes = _re.findall(r'^class\s+(\w+)', user_code, _re.MULTILINE)
    node_classes = [c for c in defined_classes if c in ('Node', 'TreeNode', 'ListNode')]
    for cls_name in node_classes:
        if f'class {cls_name}' not in test_code:
            # Extract the class definition from user_code and prepend to test
            # Updated regex: handles blank lines inside class body
            pattern = _re.compile(
                rf'^(class\s+{cls_name}\b[^\n]*:\s*\n(?:(?:[ \t]+[^\n]*|\s*)\n)*)',
                _re.MULTILINE
            )
            match = pattern.search(user_code)
            if match:
                test_code = match.group(0) + '\n' + test_code
                print(f"[NODE CLASS] Injected '{cls_name}' class into test script")
    return test_code


# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"message": "SkillSync Backend is Live!"}

@app.post("/execute")
async def execute_code(payload: RunPayload):
    """
    Execute user code with either sample tests (Run Code) or comprehensive tests (Submit).
    """
    print(f"Executing Code Length: {len(payload.code)} chars | Mode: {'SUBMIT' if payload.is_submit else 'RUN'}")

    # ─── SAFETY IMPORT HEADER ──────────────────────────────────────────────
    # LLMs sometimes forget to include `from typing import ...` in generated code.
    # This header ensures all standard imports are always available, preventing
    # NameError on common type hints (Optional, List, Dict, etc.) and utilities.
    SAFETY_IMPORTS = """# --- Auto-injected safety imports ---
import sys
import math
import heapq
from typing import List, Optional, Dict, Set, Tuple, Any
from collections import defaultdict, deque, Counter
# --- End safety imports ---
"""

    # SANITIZE: Ensure code fields are non-None strings
    user_code = payload.code or ""
    sample_tests_raw = payload.sample_tests or ""
    comprehensive_tests_raw = payload.comprehensive_tests or ""

    # Fix double-escaped newlines in test code (Gemini sometimes double-encodes)
    sample_tests_raw = _fix_code_escaping(sample_tests_raw)
    comprehensive_tests_raw = _fix_code_escaping(comprehensive_tests_raw)

    # SANITIZE: Strip any duplicate `class Solution:` from test scripts
    # The LLM sometimes includes a dummy Solution class that overrides the user's code
    clean_sample = _strip_solution_class_from_tests(sample_tests_raw)
    clean_comprehensive = _strip_solution_class_from_tests(comprehensive_tests_raw)

    # DUAL TESTING: Choose which test suite to stitch based on is_submit flag
    full_code = user_code
    if payload.is_submit and clean_comprehensive:
        full_code = user_code + "\n\n" + clean_comprehensive
        print(f"Stitched COMPREHENSIVE tests ({len(clean_comprehensive)} chars)")
    elif clean_sample:
        full_code = user_code + "\n\n" + clean_sample
        print(f"Stitched SAMPLE tests ({len(clean_sample)} chars)")

    # Prepend safety imports (won't conflict — Python ignores duplicate imports)
    full_code = SAFETY_IMPORTS + full_code

    # PRE-FLIGHT: Check for SyntaxError from LLM-generated bracket mismatches.
    # The LLM sometimes generates deeply nested tree literals like [1,[2,[3,[4,[5]]]]]
    # with mismatched brackets. Rather than crash, we remove the broken lines.
    full_code = _fix_syntax_errors(full_code)

    # 1. Create a secure, temporary Python file with UTF-8 encoding (fixes Windows Unicode error)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(full_code)
        temp_file_path = temp_file.name

    try:
        # 2. Run the temporary file - longer timeout for comprehensive tests
        timeout_seconds = 30 if payload.is_submit else 5

        # Fix Windows Unicode error: Force UTF-8 encoding for subprocess stdout/stderr
        subprocess_env = os.environ.copy()
        subprocess_env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            [sys.executable, temp_file_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=subprocess_env,
            encoding="utf-8",
            errors="replace"
        )

        # 3. Filter out the harmless Windows Python warning from stderr
        stderr_output = result.stderr.strip()
        stderr_lines = stderr_output.split('\n')
        filtered_stderr = '\n'.join([
            line for line in stderr_lines
            if "Could not find platform independent libraries" not in line
        ]).strip()

        return {
            "stdout": result.stdout.strip(),
            "stderr": filtered_stderr,
            "is_submit": payload.is_submit
        }

    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Error: Execution timed out (Possible infinite loop detected)."
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"System Error: Could not execute code locally. {str(e)}"
        }
    finally:
        # 3. Always clean up the temp file so we don't clutter your hard drive
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/submit")
async def evaluate_submission(payload: SubmissionPayload):
    print(f"Evaluating: {payload.attempts} attempts, {len(payload.logs)} error logs.")

    # --- 1. RUN THE STATIC AST ANALYSIS FIRST ---
    ast_data = analyze_code_ast(payload.code)
    print(f"AST Analysis Result: {ast_data}")

    # --- 2. RUN ORIGINALITY ANALYSIS (Pure Python — no Java/JPlag needed) ---
    originality_report = analyze_originality(
        code=payload.code,
        skeleton="",  # Single-question mode: no skeleton available
        attempts=payload.attempts,
        error_count=len(payload.logs),
        tab_switches=payload.tab_switches,
        paste_count=payload.paste_count,
    )
    originality_score = originality_report.originality_score
    print(f"Originality Analysis: score={originality_score}, verdict={originality_report.verdict}")
    print(f"  Signals: {', '.join(f'{s.name}={s.suspicion:.0f}' for s in originality_report.signals)}")

    # --- 3. CHECK API KEY ---
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is missing!")
        return {
            "logic_score": 0, "resilience_score": 0,
            "clean_code_score": 0, "debugging_score": 0,
            "originality_score": originality_score,
            "executive_summary": "SYSTEM ERROR: GEMINI_API_KEY not found in .env file. Please add it and restart the server."
        }

    # --- 4. INITIALIZE GOOGLE GENAI CLIENT ---
    client = genai.Client(api_key=api_key)

    # --- 5. BUILD THE ORIGINALITY/PENALIZATION BLOCK FOR LLM ---
    originality_instruction = f"""
    ORIGINALITY ANALYSIS (computed by multi-signal heuristic engine):
    originality_score = {originality_score}/100
    verdict = "{originality_report.verdict}"

    Signal Breakdown:
    {originality_report.explanation}
    """

    if originality_score < 40:
        originality_instruction += """
    ██████████████████████████████████████████████████████████████████████████
    ██  CRITICAL: LIKELY PLAGIARISM DETECTED — MANDATORY PENALIZATION!    ██
    ██████████████████████████████████████████████████████████████████████████

    The originality_score is BELOW 40 (likely_copied). MANDATORY rules:

    1. You MUST cap logic_score at a MAXIMUM of 15 out of 100.
    2. You MUST cap resilience_score at a MAXIMUM of 15 out of 100.
    3. You MUST cap clean_code_score at a MAXIMUM of 15 out of 100.
    4. The executive_summary MUST begin with EXACTLY this sentence:
       "Academic integrity violation detected. Code submission shows strong signs of being copied or AI-generated."
    5. debugging_score can remain unaffected.

    DO NOT IGNORE THIS RULE. Scores above 15 when originality < 40 are INVALID.
    """
    elif originality_score < 70:
        originality_instruction += """
    ⚠️ SUSPICIOUS ORIGINALITY — PARTIAL PENALIZATION:
    The originality_score is between 40-69 (suspicious). You should:
    1. Reduce logic_score and clean_code_score by 20-40 points from what you'd otherwise give.
    2. Mention the suspicion in the executive_summary.
    """

    # --- 6. THE UPGRADED GOD PROMPT (WITH AST DATA + ORIGINALITY) ---
    prompt = f"""
    You are an elite Technical Hiring Manager evaluating a candidate's coding simulation.

    CANDIDATE TELEMETRY:
    Final Code:
    {payload.code}

    Total Execution Attempts: {payload.attempts}
    Error Logs Encountered (The Struggle): {payload.logs}

    STATIC ANALYSIS (AST DATA):
    {ast_data}

    ANTI-CHEAT TELEMETRY:
    Tab switches during session: {payload.tab_switches}
    Code paste events (>20 chars): {payload.paste_count}
    {"⚠️ HIGH TAB SWITCHING: " + str(payload.tab_switches) + " tab switches is suspicious. Mention this in the executive_summary." if payload.tab_switches >= 5 else ""}
    {"⚠️ CODE PASTING DETECTED: " + str(payload.paste_count) + " paste event(s). Consider this when evaluating originality." if payload.paste_count >= 1 else ""}

    {originality_instruction}

    TASK:
    Analyze the telemetry and provide a JSON assessment.
    1. logic_score (0-100): Does the code solve the problem?
    2. resilience_score (0-100): Did they fix errors systematically based on the logs?
    3. clean_code_score (0-100): Code quality, naming, structure. Deduct for high complexity.
    4. debugging_score (0-100): How well did they interpret the terminal errors?

    CRITICAL: If originality_score < 40, you MUST cap logic_score, resilience_score,
    and clean_code_score at 15 maximum. This is NON-NEGOTIABLE.
    If originality_score is 40-69, reduce scores by 20-40 points and note suspicion.

    OUTPUT SCHEMA MUST BE EXACTLY THIS JSON:
    {{
      "logic_score": 85,
      "resilience_score": 90,
      "clean_code_score": 70,
      "debugging_score": 88,
      "executive_summary": "A short summary here."
    }}
    """

    try:
        # Use new google.genai client API
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        raw_text = response.text.strip()

        # Aggressive Markdown Stripping (The Hackathon Safety Net)
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        clean_json_string = raw_text.strip()

        # Parse the AI response
        result = safe_json_loads(clean_json_string)

        # --- SERVER-SIDE ENFORCEMENT: Hard cap if originality < 40 ---
        # Don't rely on the LLM alone — enforce the cap deterministically
        if originality_score < 40:
            print(f"[ORIGINALITY ENFORCEMENT] Score is {originality_score}/100 (likely_copied). Capping scores at 15.")
            result["logic_score"] = min(result.get("logic_score", 0), 15)
            result["resilience_score"] = min(result.get("resilience_score", 0), 15)
            result["clean_code_score"] = min(result.get("clean_code_score", 0), 15)
            integrity_prefix = "Academic integrity violation detected. Code submission shows strong signs of being copied or AI-generated."
            existing_summary = result.get("executive_summary", "")
            if not existing_summary.startswith(integrity_prefix):
                result["executive_summary"] = f"{integrity_prefix} {existing_summary}"
        elif originality_score < 70:
            print(f"[ORIGINALITY WARNING] Score is {originality_score}/100 (suspicious). Applying partial penalty.")
            # Reduce scores by 20% as a soft penalty
            for key in ["logic_score", "resilience_score", "clean_code_score"]:
                if key in result:
                    result[key] = max(0, int(result[key] * 0.8))

        # Inject originality score into the response for frontend
        result["originality_score"] = originality_score

        # --- PROCTORING INTEGRITY PENALTY ---
        if payload.proctoring_data:
            proctor_integrity = payload.proctoring_data.get("integrity_score", 100)
            if proctor_integrity < 40:
                penalty = 0.70  # 30% reduction
                print(f"[PROCTOR PENALTY] Integrity {proctor_integrity}% — applying 30% score reduction")
                result["executive_summary"] = f"⚠️ Proctoring integrity critically low ({proctor_integrity}%). " + result.get("executive_summary", "")
            elif proctor_integrity < 60:
                penalty = 0.85  # 15% reduction
                print(f"[PROCTOR PENALTY] Integrity {proctor_integrity}% — applying 15% score reduction")
            elif proctor_integrity < 80:
                penalty = 0.95  # 5% reduction
                print(f"[PROCTOR PENALTY] Integrity {proctor_integrity}% — applying 5% score reduction")
            else:
                penalty = 1.0  # No penalty

            if penalty < 1.0:
                for key in ["logic_score", "resilience_score", "clean_code_score", "debugging_score"]:
                    if key in result:
                        result[key] = max(0, int(result[key] * penalty))

            result["proctor_integrity"] = proctor_integrity

        return result

    except Exception as e:
        print(f"AI Parsing Error: {e}")
        print(f"Raw AI Output was: {response.text if 'response' in locals() else 'No response'}")

        # The Demo Fallback
        return {
            "logic_score": 50, "resilience_score": 50,
            "clean_code_score": 50, "debugging_score": 50,
            "originality_score": originality_score,
            "executive_summary": f"Demo fallback: AI encountered an error processing the results. {str(e)}"
        }


# ============================================================
# BATCH EVALUATION ENDPOINT — Evaluates all 4 questions at once
# ============================================================

@app.post("/batch-submit")
async def batch_evaluate(payload: BatchEvalPayload):
    """
    Evaluates all 4 question submissions holistically.
    Called by React when user clicks 'AI Evaluate' in batch mode.
    """
    print(f"Batch Evaluation: {len(payload.questions)} questions received")
    for i, q in enumerate(payload.questions):
        print(f"  Q{i+1} [{q.question_type}]: {q.attempts} attempts, {len(q.logs)} errors, {len(q.code)} chars")

    # --- 1. RUN ORIGINALITY ANALYSIS across all questions ---
    questions_for_analysis = [
        {
            "code": q.code,
            "skeleton": "",  # Skeleton not available in batch eval payload
            "attempts": q.attempts,
            "error_count": len(q.logs),
        }
        for q in payload.questions
    ]
    originality_report = analyze_batch_originality(
        questions_for_analysis,
        tab_switches=payload.tab_switches,
        paste_count=payload.paste_count,
    )
    originality_score = originality_report.originality_score
    print(f"Batch Originality Analysis: score={originality_score}, verdict={originality_report.verdict}")

    # --- 2. CHECK API KEY ---
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is missing!")
        return {
            "logic_score": 0, "resilience_score": 0,
            "clean_code_score": 0, "debugging_score": 0,
            "originality_score": originality_score,
            "executive_summary": "SYSTEM ERROR: GEMINI_API_KEY not found."
        }

    # --- 3. BUILD HOLISTIC PROMPT ---
    client = genai.Client(api_key=api_key)

    # Compose telemetry for all questions
    questions_telemetry = ""
    for i, q in enumerate(payload.questions):
        error_logs_text = "\n".join([f"  Attempt {log.attempt}: {log.log[:200]}" for log in q.logs[:5]])
        if not error_logs_text:
            error_logs_text = "  (no errors logged)"
        questions_telemetry += f"""
    ━━━━━━━━━ QUESTION {i+1}: {q.question_type.upper()} ━━━━━━━━━
    Title: {q.title}
    Code ({len(q.code)} chars):
    {q.code[:2000]}

    Execution Attempts: {q.attempts}
    Error Logs:
{error_logs_text}
    """

    # Build originality instruction for the LLM
    originality_instruction = f"""
    ORIGINALITY ANALYSIS (computed by multi-signal heuristic engine):
    originality_score = {originality_score}/100
    verdict = "{originality_report.verdict}"

    {originality_report.explanation}
    """

    if originality_score < 40:
        originality_instruction += """
    ██████████████████████████████████████████████████████████████████████████
    ██  CRITICAL: LIKELY PLAGIARISM DETECTED — MANDATORY PENALIZATION!    ██
    ██████████████████████████████████████████████████████████████████████████

    The originality_score is BELOW 40. MANDATORY rules:
    1. Cap logic_score, resilience_score, clean_code_score at 15 MAXIMUM.
    2. executive_summary MUST start with: "Academic integrity violation detected."
    3. DO NOT give high scores. This is NON-NEGOTIABLE.
    """
    elif originality_score < 70:
        originality_instruction += """
    ⚠️ SUSPICIOUS ORIGINALITY — PARTIAL PENALIZATION:
    Reduce logic_score and clean_code_score by 20-40 points.
    Mention the suspicion in the executive_summary.
    """

    prompt = f"""
    You are an elite Technical Hiring Manager performing a HOLISTIC cognitive evaluation
    of a candidate who completed a 4-question coding assessment.

    The assessment included:
    - Question 1 (scratch): Write a solution from scratch
    - Question 2 (logic_bug): Find and fix logic errors
    - Question 3 (syntax_error): Fix syntax/scope errors
    - Question 4 (optimization): Optimize O(N squared) to O(N)

    CANDIDATE TELEMETRY ACROSS ALL 4 QUESTIONS:
    {questions_telemetry}

    ANTI-CHEAT TELEMETRY:
    Tab switches during session: {payload.tab_switches}
    Code paste events (>20 chars): {payload.paste_count}
    {"⚠️ HIGH TAB SWITCHING: " + str(payload.tab_switches) + " switches detected. Mention in executive_summary." if payload.tab_switches >= 5 else ""}
    {"⚠️ CODE PASTING DETECTED: " + str(payload.paste_count) + " paste event(s). Factor into originality assessment." if payload.paste_count >= 1 else ""}

    {originality_instruction}

    TASK:
    Provide a SINGLE holistic JSON assessment across all 4 questions.
    Weight each question type appropriately:
    - scratch → tests raw problem-solving (logic_score)
    - logic_bug → tests debugging intuition (debugging_score)
    - syntax_error → tests language mastery (clean_code_score)
    - optimization → tests resilience and algorithmic thinking (resilience_score)

    CRITICAL: If originality_score < 40, cap logic_score, resilience_score,
    and clean_code_score at 15 maximum. NON-NEGOTIABLE.

    OUTPUT SCHEMA MUST BE EXACTLY THIS JSON:
    {{
      "logic_score": 85,
      "resilience_score": 90,
      "clean_code_score": 70,
      "debugging_score": 88,
      "executive_summary": "A concise 2-3 sentence holistic assessment."
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        raw_text = response.text.strip()

        # Markdown stripping
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        result = safe_json_loads(raw_text.strip())

        # Server-side originality enforcement
        if originality_score < 40:
            print(f"[BATCH ORIGINALITY ENFORCEMENT] Score {originality_score}/100. Capping at 15.")
            result["logic_score"] = min(result.get("logic_score", 0), 15)
            result["resilience_score"] = min(result.get("resilience_score", 0), 15)
            result["clean_code_score"] = min(result.get("clean_code_score", 0), 15)
            integrity_prefix = "Academic integrity violation detected. Code submission shows strong signs of being copied or AI-generated."
            existing_summary = result.get("executive_summary", "")
            if not existing_summary.startswith(integrity_prefix):
                result["executive_summary"] = f"{integrity_prefix} {existing_summary}"
        elif originality_score < 70:
            print(f"[BATCH ORIGINALITY WARNING] Score {originality_score}/100. Partial penalty.")
            for key in ["logic_score", "resilience_score", "clean_code_score"]:
                if key in result:
                    result[key] = max(0, int(result[key] * 0.8))

        # Add originality score for frontend
        result["originality_score"] = originality_score

        # --- PROCTORING INTEGRITY PENALTY ---
        if payload.proctoring_data:
            proctor_integrity = payload.proctoring_data.get("integrity_score", 100)
            if proctor_integrity < 40:
                penalty = 0.70
                print(f"[BATCH PROCTOR PENALTY] Integrity {proctor_integrity}% — 30% reduction")
                result["executive_summary"] = f"⚠️ Proctoring integrity critically low ({proctor_integrity}%). " + result.get("executive_summary", "")
            elif proctor_integrity < 60:
                penalty = 0.85
                print(f"[BATCH PROCTOR PENALTY] Integrity {proctor_integrity}% — 15% reduction")
            elif proctor_integrity < 80:
                penalty = 0.95
                print(f"[BATCH PROCTOR PENALTY] Integrity {proctor_integrity}% — 5% reduction")
            else:
                penalty = 1.0

            if penalty < 1.0:
                for key in ["logic_score", "resilience_score", "clean_code_score", "debugging_score"]:
                    if key in result:
                        result[key] = max(0, int(result[key] * penalty))

            result["proctor_integrity"] = proctor_integrity

        return result

    except Exception as e:
        print(f"Batch AI Evaluation Error: {e}")
        print(f"Raw AI Output: {response.text if 'response' in locals() else 'No response'}")
        return {
            "logic_score": 50, "resilience_score": 50,
            "clean_code_score": 50, "debugging_score": 50,
            "originality_score": originality_score,
            "executive_summary": f"Demo fallback: AI evaluation encountered an error. {str(e)}"
        }


# ============================================================
# OMNIPARSE AI - INTELLIGENT DOCUMENT PROCESSING ENGINE
# ============================================================

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text content from PDF using PyMuPDF."""
    try:
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in pdf_document:
            text += page.get_text()
        pdf_document.close()
        return text[:8000]  # Limit to prevent token overflow
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF parsing failed: {str(e)}")


def extract_text_from_url(url: str) -> str:
    """Scrape and extract text from a URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Extract text from relevant tags
        paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li', 'pre', 'code', 'td', 'th'])
        text = " ".join([p.get_text(strip=True) for p in paragraphs])

        return text[:8000]  # Limit to prevent token overflow
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL scraping failed: {str(e)}")


def analyze_with_gemini(text_content: str, source_type: str) -> dict:
    """Use Gemini AI to perform intelligent document analysis."""
    api_key = os.getenv("GEMINI_API_KEY")

    # Early return if no API key
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in environment!")
        print("   Please ensure you have a .env file with GEMINI_API_KEY=your_key")
        return get_fallback_response()

    print(f"API Key found (starts with: {api_key[:10]}...)")

    try:
        # Initialize the new google.genai client
        client = genai.Client(api_key=api_key)

        prompt = f"""
    You are an expert LeetCode problem setter and Senior Staff Engineer. Read the following excerpt and create a highly specific, production-grade Python coding challenge based on the concepts taught.

    EXCERPT:
    {text_content}

    SOURCE: {source_type}

    TASK:
    Generate a complete coding scenario. You must output a strict JSON object with exactly these keys: "category", "confidence", "summary", "key_metrics", "insights", "recommendations", "user_code", "sample_tests", "comprehensive_tests".

    ============================================================
    PART 1: METADATA
    ============================================================

    1. "category": Classify as one of: "Data Structures & Algorithms", "System Design", "Business Logic", "Machine Learning", "Database Schema", "General Technical Document"

    2. "confidence": Confidence level like "High (95%)" or "Medium (80%)"

    3. "key_metrics": Object with "complexity", "type", "difficulty" fields

    4. "insights": Array of 3-5 key learning points

    5. "recommendations": Array of 2-3 practice tips

    ============================================================
    PART 2: PROBLEM DESCRIPTION ("summary")
    ============================================================

    Format as a readable LeetCode-style problem in Markdown:

    ## Problem Statement
    [Clear description - DO NOT give away the algorithm]

    ## Examples
    **Example 1:**
    Input: [specific input]
    Output: [expected output]
    Explanation: [brief explanation]

    **Example 2:**
    Input: [another input]
    Output: [expected output]

    ## Constraints
    - [constraint 1]
    - [constraint 2]

    ============================================================
    PART 3: USER CODE ("user_code") - CRITICAL RULES
    ============================================================

    The user_code is what the candidate sees in the editor. It must be a MINIMAL SKELETON with NO SOLUTION HINTS.

    STRUCTURE (follow this EXACTLY):
    ```python
    from typing import List, Optional, Dict, Set, Tuple

    # If custom data structure needed (Node, TreeNode, ListNode, etc.):
    class Node:
        def __init__(self, val: int = 0):
            self.val = val
            self.children: List['Node'] = []

    class Solution:
        def methodName(self, param1: List[int], param2: int) -> int:
            \"\"\"
            Brief description of what to compute.

            Args:
                param1: Description of first parameter
                param2: Description of second parameter

            Returns:
                Description of return value
            \"\"\"
            pass
    ```

    RULES:
    - ALWAYS include `from typing import List, Optional, Dict, Set, Tuple` at the TOP
    - If problem needs Node/TreeNode/ListNode, define the class with type hints
    - Solution class with ONE target method
    - Method has FULL type hints for ALL parameters and return type
    - Google-style docstring explaining args and return
    - Method body is ONLY `pass` - NO pseudocode, NO hints, NO comments about algorithm
    - NO variable names that hint at solution

    ============================================================
    PART 4: SAMPLE TESTS ("sample_tests") - 3 Test Cases
    ============================================================

    This is for the "Run Code" button. It must be a COMPLETE, STANDALONE Python script.

    CRITICAL: The sample_tests script must RE-DEFINE everything needed:
    - All imports (typing, sys, etc.)
    - All class definitions (Node, TreeNode, etc.) - COPY them from user_code
    - The Solution class is NOT included here - it comes from user's code

    ████████████████████████████████████████████████████████████████████████████
    ██  NUCLEAR WARNING — DO NOT OUTPUT `class Solution` IN TEST SCRIPTS!  ██
    ████████████████████████████████████████████████████████████████████████████

    The test scripts (sample_tests and comprehensive_tests) are STITCHED AFTER
    the user's code at runtime like this:
        full_code = user_code + "\n\n" + test_script

    If your test script contains `class Solution:`, it OVERWRITES the user's
    real Solution class. Every method call then returns None. ALL TESTS FAIL.

    RULES:
    1. NEVER include `class Solution` in sample_tests or comprehensive_tests.
    2. The test scripts must assume `Solution` already exists from user's code.
    3. Test scripts should ONLY contain: imports, helper functions
       (Node, TreeNode, build_tree_from_edges, compute_expected),
       and the `if __name__ == '__main__':` test execution block.
    4. Start the test block with `solution = Solution()` — do NOT redefine it.

    ANTI-HALLUCINATION RULE — ABSOLUTE BAN ON NESTED ARRAYS FOR TREES:
    NEVER use nested lists like [1, [2, [5], [6]], [3]] for tree data.
    The LLM ALWAYS miscounts brackets in nested arrays, causing SyntaxError.
    Instead, use FLAT EDGE LISTS: root_val + list of (parent, child) tuples.

    TEMPLATE FOR TREE PROBLEMS:
    ```python
    import sys
    from typing import List, Optional, Dict, Set, Tuple
    from collections import defaultdict

    class Node:
        def __init__(self, val: int = 0):
            self.val = val
            self.children: List['Node'] = []

    def build_tree_from_edges(root_val, edges):
        \\\"\\\"\\\"Build N-ary tree from root value + flat edge list.
        edges = [(parent_val, child_val), ...]
        \\\"\\\"\\\"
        if root_val is None:
            return None
        nodes = {{root_val: Node(root_val)}}
        for parent, child in edges:
            if parent not in nodes:
                nodes[parent] = Node(parent)
            if child not in nodes:
                nodes[child] = Node(child)
            nodes[parent].children.append(nodes[child])
        return nodes[root_val]

    def compute_expected(root):
        \\\"\\\"\\\"REFERENCE IMPLEMENTATION — computes the correct answer.
        This function must implement the CORRECT algorithm so expected
        values are COMPUTED, never guessed or hardcoded.
        REPLACE THIS BODY with the correct logic for this specific problem.
        \\\"\\\"\\\"
        # Example for maxDepth (counting nodes along longest path):
        if not root:
            return 0
        if not root.children:
            return 1
        return 1 + max(compute_expected(child) for child in root.children)

    if __name__ == '__main__':
        solution = Solution()
        passed = 0
        total = 3

        # --- Test cases as data: (root_val, edges, description) ---
        test_cases = [
            (1, [(1,2), (1,3), (1,4), (2,5), (2,6)], "Multi-level tree"),
            (1, [], "Single node"),
            (None, [], "Empty tree"),
        ]

        for i, (root_val, edges, desc) in enumerate(test_cases, 1):
            tree = build_tree_from_edges(root_val, edges) if root_val is not None else None
            expected = compute_expected(tree)
            try:
                actual = solution.methodName(tree)
            except Exception as e:
                print(f"Runtime Error: {{passed}} / {{total}} testcases passed")
                print(f"Error Message: {{e}}")
                sys.exit(1)

            print(f"--- Test Case {{i}} ---")
            print(f"Input: root={{root_val}}, edges={{edges}}")
            print(f"Expected: {{expected}}")
            print(f"Actual: {{actual}}")
            if actual == expected:
                print("Status: PASS")
                passed += 1
            else:
                print("Status: FAIL")
            print()

        if passed == total:
            print(f"All Tests Passed: {{passed}}/{{total}}")
        else:
            print(f"Wrong Answer: {{passed}} / {{total}} testcases passed")
    ```

    ████████████████████████████████████████████████████████████████████████
    ██  CRITICAL: compute_expected() IS MANDATORY — NOT OPTIONAL!       ██
    ████████████████████████████████████████████████████████████████████████

    You MUST include a compute_expected() function in EVERY test script.
    This function must contain the CORRECT reference implementation.
    ALL expected values must be computed by calling compute_expected(),
    NEVER by hardcoding numbers. If you hardcode expected = 4, that is
    a HALLUCINATION BUG. The function exists to prevent exactly this.

    TEMPLATE FOR SIMPLE ARRAY PROBLEMS:
    ```python
    import sys
    from typing import List, Optional, Dict, Set, Tuple

    def compute_expected(*args):
        \\\"\\\"\\\"REFERENCE IMPLEMENTATION — computes the correct answer.
        REPLACE THIS BODY with the correct algorithm for this problem.
        \\\"\\\"\\\"
        # Example for twoSum:
        # nums, target = args
        # for i in range(len(nums)):
        #     for j in range(i+1, len(nums)):
        #         if nums[i] + nums[j] == target:
        #             return [i, j]
        # return []
        pass

    if __name__ == '__main__':
        solution = Solution()
        passed = 0
        total = 3

        # --- Test cases as data: (inputs_tuple, description) ---
        test_cases = [
            (([1, 2, 3],), "Basic array"),
            (([5],), "Single element"),
            (([],), "Empty array"),
        ]

        for i, (inputs, desc) in enumerate(test_cases, 1):
            expected = compute_expected(*inputs)
            try:
                actual = solution.methodName(*inputs)
            except Exception as e:
                print(f"Runtime Error: {{passed}} / {{total}} testcases passed")
                print(f"Error Message: {{e}}")
                sys.exit(1)

            print(f"--- Test Case {{i}} ---")
            print(f"Input: {{inputs}}")
            print(f"Expected: {{expected}}")
            print(f"Actual: {{actual}}")
            if actual == expected:
                print("Status: PASS")
                passed += 1
            else:
                print("Status: FAIL")
            print()

        if passed == total:
            print(f"All Tests Passed: {{passed}}/{{total}}")
        else:
            print(f"Wrong Answer: {{passed}} / {{total}} testcases passed")
    ```

    ============================================================
    PART 5: COMPREHENSIVE TESTS ("comprehensive_tests") - BULLETPROOF ARCHITECTURE
    ============================================================

    ABSOLUTE ZERO-HALLUCINATION PROTOCOL 

    This section generates the test runner for the "Submit" button.
    YOU MUST FOLLOW THESE RULES EXACTLY TO PREVENT CRASHES.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RULE 1: FORBIDDEN - MANUAL VARIABLE SPRAWL
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ABSOLUTELY FORBIDDEN - DO NOT DO THIS:
    ```python
    # This WILL cause NameError due to typos - NEVER DO THIS!
    tc1_node_a = Node(1)
    tc1_node_b = Node(2)
    tc1_node_c = Node(3)
    tc2_root_x = Node(10)
    tc2_child_y = Node(20)
    tc24_c30_149 = Node(149)
    tc24_c30_149.children = [tc24_g2_153]  # NameError: tc24_g2_153 not defined!
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RULE 2: MANDATORY - USE DETERMINISTIC HELPER FUNCTIONS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    For ANY problem involving Trees, Graphs, or Linked Lists, you MUST
    write a helper function that builds the structure from FLAT data.

    ██████████████████████████████████████████████████████████████
    ██  ABSOLUTE BAN: NEVER use nested lists for tree data!     ██
    ██  BANNED: [1, [2, [5], [6]], [3]]  <-- WILL CRASH!       ██
    ██  BANNED: build_tree(nested_list)  <-- FORBIDDEN!         ██
    ██  REQUIRED: Flat edge tuples: [(1,2), (1,3), (2,5)]      ██
    ██████████████████████████████████████████████████████████████

    REQUIRED HELPER FUNCTIONS BY PROBLEM TYPE:

    FOR N-ARY TREES (MANDATORY — use this EXACT function):
    ```python
    def build_tree_from_edges(root_val, edges):
        \"\"\"Build N-ary tree from root value + flat edge list.
        edges = [(parent_val, child_val), ...]
        Example: root_val=1, edges=[(1,2), (1,3), (1,4), (2,5), (2,6), (4,7)]
        \"\"\"
        from collections import defaultdict
        nodes = {{root_val: Node(root_val)}}
        for parent, child in edges:
            if parent not in nodes:
                nodes[parent] = Node(parent)
            if child not in nodes:
                nodes[child] = Node(child)
            nodes[parent].children.append(nodes[child])
        return nodes[root_val]
    ```

    FOR BINARY TREES (MANDATORY — flat level-order list, NO nesting):
    ```python
    def build_binary_tree(data):
        \"\"\"Build binary tree from level-order list: [1, 2, 3, None, 4, 5, None]\"\"\"
        if not data or data[0] is None:
            return None
        root = TreeNode(data[0])
        queue = [root]
        i = 1
        while queue and i < len(data):
            node = queue.pop(0)
            if i < len(data) and data[i] is not None:
                node.left = TreeNode(data[i])
                queue.append(node.left)
            i += 1
            if i < len(data) and data[i] is not None:
                node.right = TreeNode(data[i])
                queue.append(node.right)
            i += 1
        return root
    ```

    FOR LINKED LISTS:
    ```python
    def build_linked_list(data):
        \"\"\"Build linked list from simple Python list: [1, 2, 3, 4]\"\"\"
        if not data:
            return None
        head = ListNode(data[0])
        curr = head
        for val in data[1:]:
            curr.next = ListNode(val)
            curr = curr.next
        return head
    ```

    FOR GRAPHS (Adjacency List):
    ```python
    def build_graph(n, edges):
        \"\"\"Build adjacency list from edge list: [(0,1), (1,2), (2,0)]\"\"\"
        graph = {{i: [] for i in range(n)}}
        for u, v in edges:
            graph[u].append(v)
            graph[v].append(u)  # Remove for directed graph
        return graph
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RULE 3: MANDATORY - DATA-DRIVEN TEST CASES (FLAT FORMAT ONLY)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    All test cases MUST be stored as FLAT Python data (tuples of root_val + edge lists).
    The helper function converts them to objects AT RUNTIME.

    CORRECT DATA-DRIVEN APPROACH (FLAT EDGE LISTS):
    ```python
    # Test data as FLAT tuples — NEVER nested arrays!
    test_cases = [
        # (root_val, edges, expected_output)
        (1, [(1,2), (1,3)], 2),                                  # Simple tree
        (10, [(10,20), (10,30), (20,40), (20,50)], 4),          # Deeper tree
        (5, [], 1),                                               # Single node (no edges)
    ]

    # For DEEP chains, generate edge list programmatically:
    def make_chain_edges(depth):
        \"\"\"Build flat edge list for a linear chain of depth n.
        Returns (root_val, edges) — NO nested lists!
        \"\"\"
        edges = [(i, i + 1) for i in range(1, depth)]
        return (1, edges)

    root_val, edges = make_chain_edges(5)
    test_cases.append((root_val, edges, 1))
    root_val, edges = make_chain_edges(10)
    test_cases.append((root_val, edges, 1))

    for i, (root_val, edges, expected) in enumerate(test_cases):
        root = build_tree_from_edges(root_val, edges)  # Convert to Node objects HERE
        actual = solution.methodName(root)
        # ... check result
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RULE 4: MANDATORY - EXPECTED VALUE CALCULATOR
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    For problems with complex expected outputs, write a REFERENCE SOLUTION
    function that computes the correct answer. This ensures mathematical
    correctness and eliminates manual calculation errors.

    REQUIRED FOR COMPLEX PROBLEMS:
    ```python
    def compute_expected(root):
        \"\"\"Reference implementation to compute correct answer.\"\"\"
        if not root:
            return [0, 0, 0]
        leaf_count, internal_count, max_children = 0, 0, 0
        def dfs(node):
            nonlocal leaf_count, internal_count, max_children
            max_children = max(max_children, len(node.children))
            if not node.children:
                leaf_count += 1
            else:
                internal_count += 1
                for child in node.children:
                    dfs(child)
        dfs(root)
        return [leaf_count, internal_count, max_children]

    # Then use it with FLAT edge-list data:
    for root_val, edges in test_data_list:
        root = build_tree_from_edges(root_val, edges)
        expected = compute_expected(root)  # Auto-calculate!
        test_cases.append((root_val, edges, expected))
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RULE 5: MANDATORY - STRICT OUTPUT FORMAT ON FAILURE
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    On FIRST failure, print EXACTLY this format and exit:
    ```
    Wrong Answer: [passed] / [total] testcases passed

    Input:
    [input_data]

    Output:
    [actual]

    Expected:
    [expected]
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    COMPLETE TEMPLATE FOR comprehensive_tests
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ```python
    import sys
    from typing import List, Optional, Dict, Set, Tuple
    from collections import defaultdict

    # ===== DATA STRUCTURE DEFINITIONS =====
    class Node:
        def __init__(self, val: int = 0):
            self.val = val
            self.children: List['Node'] = []

    # ===== HELPER: Build tree from FLAT edge list (MANDATORY) =====
    def build_tree_from_edges(root_val, edges):
        \"\"\"Build N-ary tree from root value + flat edge list.
        edges = [(parent_val, child_val), ...]
        NEVER use nested lists — they cause bracket SyntaxErrors!
        \"\"\"
        nodes = {{root_val: Node(root_val)}}
        for parent, child in edges:
            if parent not in nodes:
                nodes[parent] = Node(parent)
            if child not in nodes:
                nodes[child] = Node(child)
            nodes[parent].children.append(nodes[child])
        return nodes[root_val]

    # ===== HELPER: Generate deep chain as FLAT edge list =====
    def make_chain_edges(depth):
        \"\"\"Build flat edge list for a linear chain of given depth.
        Returns (root_val, edges) — NO nested lists!
        \"\"\"
        edges = [(i, i + 1) for i in range(1, depth)]
        return (1, edges)

    # ===== REFERENCE SOLUTION: Compute expected values =====
    def compute_expected(root):
        \"\"\"Reference implementation for validation.\"\"\"
        # Implement the correct logic here
        pass  # Replace with actual logic

    # ===== TEST EXECUTION =====
    if __name__ == '__main__':
        solution = Solution()

        # ===== TEST DATA: Flat edge-list tuples ONLY! =====
        # Format: (root_val, [(parent, child), ...])  — NEVER nested arrays!
        test_data = [
            # Basic cases from problem examples
            (1, [(1,2), (1,3), (1,4), (2,5), (2,6), (4,7)]),   # Example 1
            (10, [(10,20), (10,30)]),                            # Example 2
            (50, []),                                             # Single node

            # Edge cases
            make_chain_edges(5),                                  # Linear chain (depth 5)
            make_chain_edges(10),                                 # Linear chain (depth 10)
            (1, [(1,2), (1,3), (2,4), (2,5), (3,6), (3,7)]),   # Balanced

            # Stress tests - generate programmatically
        ]

        # Add programmatically generated cases
        for i in range(10, 30):
            edges = []
            num_children = (i % 5) + 1
            for c in range(num_children):
                child_val = i * 10 + c
                edges.append((i, child_val))
                num_grandchildren = i % 3
                for g in range(num_grandchildren):
                    grandchild_val = i * 100 + c * 10 + g
                    edges.append((child_val, grandchild_val))
            test_data.append((i, edges))

        # Build test cases with computed expected values
        test_cases = []
        for root_val, edges in test_data:
            root = build_tree_from_edges(root_val, edges)
            expected = compute_expected(root)
            test_cases.append((root_val, edges, expected))

        # ===== TEST RUNNER =====
        total = len(test_cases)
        for i, (root_val, edges, expected) in enumerate(test_cases):
            root = build_tree_from_edges(root_val, edges)
            try:
                actual = solution.methodName(root)
            except Exception as e:
                print(f"Runtime Error: {{i}} / {{total}} testcases passed")
                print()
                print(f"Input:")
                print(f"root={{root_val}}, edges={{edges}}")
                print()
                print(f"Error Message: {{e}}")
                sys.exit(1)

            if actual != expected:
                print(f"Wrong Answer: {{i}} / {{total}} testcases passed")
                print()
                print(f"Input:")
                print(f"root={{root_val}}, edges={{edges}}")
                print()
                print(f"Output:")
                print(f"{{actual}}")
                print()
                print(f"Expected:")
                print(f"{{expected}}")
                sys.exit(0)

        print(f"Accepted: {{total}}/{{total}} testcases passed")
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    FOR SIMPLE ARRAY/STRING PROBLEMS (no complex structures):
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    If the problem only uses arrays, strings, or integers, use this simpler format:

    ```python
    import sys
    from typing import List

    if __name__ == '__main__':
        solution = Solution()

        test_cases = [
            ([1, 2, 3], 6),
            ([-1, 0, 1], 0),
            ([100], 100),
            ([], 0),
            (list(range(100)), 4950),
            # ... 20+ cases
        ]

        total = len(test_cases)
        for i, (input_data, expected) in enumerate(test_cases):
            try:
                actual = solution.methodName(input_data)
            except Exception as e:
                print(f"Runtime Error: {{i}} / {{total}} testcases passed")
                print(f"Error: {{e}}")
                sys.exit(1)

            if actual != expected:
                print(f"Wrong Answer: {{i}} / {{total}} testcases passed")
                print()
                print(f"Input:")
                print(f"{{input_data}}")
                print()
                print(f"Output:")
                print(f"{{actual}}")
                print()
                print(f"Expected:")
                print(f"{{expected}}")
                sys.exit(0)

        print(f"Accepted: {{total}}/{{total}} testcases passed")
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    VALIDATION CHECKLIST FOR comprehensive_tests
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Before outputting, verify:
    [ ] NO manual Node/TreeNode instantiation with unique variable names
    [ ] NO nested lists for tree data — ONLY flat edge tuples
    [ ] Helper function (build_tree_from_edges, build_graph, etc.) is defined
    [ ] All test data is simple Python lists/tuples/dicts
    [ ] compute_expected() function exists for complex outputs
    [ ] Test runner builds objects AT RUNTIME using helper functions
    [ ] Failure output matches EXACT format specified
    [ ] At least 20 test cases covering all edge cases
    [ ] sys.exit(0) on wrong answer, sys.exit(1) on runtime error

    ============================================================
    MATHEMATICAL CORRECTNESS RULES FOR TEST CASES
    ============================================================

    CRITICAL: When generating expected outputs, you MUST strictly adhere to
    computer science definitions. DO NOT generate lazy/incorrect test cases!

    RELATIONSHIP-BASED TREE PROBLEMS:
    - COUSINS: Nodes on the same level with DIFFERENT parents.
      Siblings (same parent) are NOT cousins. Do NOT just return all nodes
      on the same level minus the target!
    - SIBLINGS: Nodes with the SAME parent.
    - ANCESTORS: All nodes on the path from root to the target (exclusive).
    - DESCENDANTS: All nodes in the subtree rooted at target (exclusive).
    - UNCLE/AUNT: Parent's siblings (parent's parent's other children).

    GRAPH PROBLEMS:
    - NEIGHBORS: Only directly connected nodes (1 edge away).
    - BFS LEVEL: Nodes at exact distance K from source.
    - CONNECTED COMPONENTS: Nodes reachable via any path.

    EXAMPLE OF CORRECT VS INCORRECT:

    Tree: 1 -> [2, 3, 4], 2 -> [5, 6], 3 -> [], 4 -> [7]

    If target = 5:
    - Level of 5: [5, 6, 7] (all at depth 2)
    - Parent of 5: Node 2
    - WRONG "cousins" of 5: [6, 7] (lazy approach: all level nodes except target)
    - CORRECT cousins of 5: [7] (only nodes with DIFFERENT parent than Node 2)
    - Node 6 is a SIBLING of 5, NOT a cousin (same parent = Node 2)

    VALIDATION: Before finalizing expected outputs, mentally trace through
    the tree structure and verify each value meets the strict CS definition.

    ============================================================
    JSON SAFETY RULES FOR ALL STRING FIELDS
    ============================================================

    Your output is parsed by json.loads(). Broken JSON = total failure.

    RULE 1 — NO ASCII ART TREE DIAGRAMS in the "description" field.
    Tree diagrams use / \\ | characters which produce invalid JSON
    escape sequences and crash the parser. Instead of:
        ```
            1
           / | \\
          2  3  4
        ```
    Use a text-based representation:
        Tree: 1 -> [2, 3, 4], 2 -> [5, 6]
    Or describe in words:
        "Root node 1 has children 2, 3, 4. Node 2 has children 5, 6."

    RULE 2 — NO BACKSLASH characters in "description", "title", or "hints".
    The only backslashes allowed in JSON string values are:
      \\n (newline), \\t (tab), \\\\ (literal backslash), \\" (escaped quote)
    Never write / \\ or | \\ or any raw backslash in prose text.

    RULE 3 — Every newline in a JSON string value MUST be \\n.
    Literal newlines break JSON parsing.

    ============================================================
    OUTPUT JSON SCHEMA (EXACT FORMAT REQUIRED)
    ============================================================

    {{
        "category": "Data Structures & Algorithms",
        "confidence": "High (95%)",
        "summary": "## Problem Statement\\n...",
        "key_metrics": {{
            "complexity": "O(N)",
            "type": "Array/Tree/Graph",
            "difficulty": "Medium"
        }},
        "insights": ["insight1", "insight2", "insight3"],
        "recommendations": ["tip1", "tip2"],
        "user_code": "from typing import List, Optional, Dict, Set, Tuple\\n\\nclass Solution:\\n    def methodName(self, nums: List[int]) -> int:\\n        \\\"\\\"\\\"...\\\"\\\"\\\"\\n        pass",
        "sample_tests": "import sys\\nfrom typing import List, Optional, Dict, Set, Tuple\\n\\nif __name__ == '__main__':\\n    ...",
        "comprehensive_tests": "import sys\\nfrom typing import List, Optional, Dict, Set, Tuple\\n\\nif __name__ == '__main__':\\n    ..."
    }}

    ============================================================
    FINAL VALIDATION CHECKLIST
    ============================================================

    Before outputting, verify:
    [ ] user_code starts with `from typing import List, Optional, Dict, Set, Tuple`
    [ ] user_code has Solution class with typed method signature
    [ ] user_code method body is ONLY `pass` with NO hints
    [ ] sample_tests starts with `import sys` and `from typing import ...`
    [ ] sample_tests re-defines any custom classes (Node, TreeNode, etc.)
    [ ] sample_tests has exactly 3 test cases
    [ ] comprehensive_tests starts with `import sys` and `from typing import ...`
    [ ] comprehensive_tests re-defines any custom classes
    [ ] comprehensive_tests has 50+ test cases
    [ ] comprehensive_tests halts on first failure with exact format
    [ ] All newlines in JSON are escaped as \\n
    [ ] RELATIONSHIP PROBLEMS: Expected outputs follow strict CS definitions
        (e.g., cousins exclude siblings, ancestors exclude self, etc.)
    [ ] TEST CASE MATH: Each expected value was computed by tracing through
        the data structure, NOT by lazy approximation
    """

        # Use new google.genai client API
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        raw_text = response.text.strip()
        print(f"Gemini Response Length: {len(raw_text)} chars")
        print(f"First 500 chars of response: {raw_text[:500]}")

        # Clean markdown formatting
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        # Sanitize and parse JSON (with robust handling of malformed Gemini JSON)
        parsed_response = safe_json_loads(raw_text.strip())
        print(f"Successfully parsed JSON with keys: {list(parsed_response.keys())}")

        # --- POST-PROCESSING: Ensure imports exist in all code fields ---
        if "user_code" in parsed_response:
            parsed_response["user_code"] = _ensure_imports_in_code(parsed_response["user_code"])
        if "sample_tests" in parsed_response:
            parsed_response["sample_tests"] = _ensure_imports_in_code(parsed_response["sample_tests"], is_test=True)
            parsed_response["sample_tests"] = _ensure_node_class_in_tests(
                parsed_response.get("user_code", ""), parsed_response["sample_tests"]
            )
        if "comprehensive_tests" in parsed_response:
            parsed_response["comprehensive_tests"] = _ensure_imports_in_code(parsed_response["comprehensive_tests"], is_test=True)
            parsed_response["comprehensive_tests"] = _ensure_node_class_in_tests(
                parsed_response.get("user_code", ""), parsed_response["comprehensive_tests"]
            )

        return parsed_response

    except json.JSONDecodeError as e:
        print(f"JSON Parsing Error: {e}")
        print(f"Raw text that failed to parse (first 1000 chars): {raw_text[:1000] if 'raw_text' in locals() else 'No response'}")
        return get_fallback_response()
    except Exception as e:
        error_str = str(e).lower()
        if "leaked" in error_str or "403" in error_str:
            print(f"API KEY ERROR: Your Gemini API key has been flagged as leaked!")
            print(f"   Please generate a new API key at: https://aistudio.google.com/app/apikey")
            print(f"   Then update your .env file with the new key.")
        elif "401" in error_str or "invalid" in error_str:
            print(f"API KEY ERROR: Invalid API key!")
            print(f"   Please check your GEMINI_API_KEY in the .env file.")
        else:
            print(f"Gemini Analysis Error: {type(e).__name__}: {e}")
        # Fallback response with proper imports
        return get_fallback_response()


def generate_batch_assessment(text_content: str, source_type: str) -> dict:
    """
    BATCH ASSESSMENT MODE: Generate exactly 4 different question types.

    Question Types:
    1. scratch - Empty function to solve from scratch
    2. logic_bug - Working code with subtle logic error to fix
    3. syntax_error - Code with syntax/scope/typing errors
    4. optimization - Inefficient brute-force to optimize
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in environment!")
        return get_fallback_batch_response()

    print(f"BATCH MODE: Generating 4 question types...")
    print(f"API Key found (starts with: {api_key[:10]}...)")

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""
    You are an expert Technical Interview Designer and LeetCode Problem Setter. 
    Read the following excerpt and create a BATCH ASSESSMENT with EXACTLY 4 DIFFERENT QUESTIONS based on the same topic/concept.

    EXCERPT:
    {text_content}

    SOURCE: {source_type}

    ============================================================
    BATCH ASSESSMENT - GENERATE EXACTLY 4 QUESTIONS
    ============================================================
    
    You MUST generate exactly 4 questions, each with a different type:
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    QUESTION 1: "scratch" - STANDARD LEETCODE PROBLEM
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    - A classic coding challenge where user writes solution from scratch
    - user_code contains ONLY the function signature and `pass`
    - NO hints, NO pseudocode, NO solution logic
    - Tests must validate correctness
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    QUESTION 2: "logic_bug" - FIND THE LOGIC ERROR
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    - A COMPLETE solution that has 1-2 SUBTLE LOGIC BUGS
    - Code runs without errors but produces WRONG OUTPUT
    - Bug types: off-by-one, wrong comparison, edge case failure, 
      incorrect variable, wrong return value
    - User must identify and fix the logic error
    - Description includes "Bug Report" section explaining it's failing tests
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    QUESTION 3: "syntax_error" - FIX THE SYNTAX/SCOPE ERRORS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    - A COMPLETE solution with 2-3 SYNTAX/SCOPE/TYPING ERRORS
    - Code does NOT run - it crashes with Python errors
    - Error types: 
      * Missing colon after if/for/def
      * Undefined variable (typo in variable name)
      * Indentation error
      * Using wrong type method (e.g., .append() on int)
      * Missing import
      * Incorrect function call (wrong arg count)
    - User must fix errors so code runs and passes tests
    - Description includes "Debug Report" explaining code won't run
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    QUESTION 4: "optimization" - OPTIMIZE THE BRUTE FORCE
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    - A COMPLETE, WORKING solution that is HIGHLY INEFFICIENT
    - Current complexity: O(N²) or O(N³) or worse
    - Target complexity: O(N) or O(N log N)
    - Code WORKS but would timeout on large inputs
    - User must refactor for better Time/Space complexity
    - Description includes "Performance Report" showing it times out
    - Include tests with large inputs that would timeout with brute force
    
    ============================================================
    ANTI-SPOILER RULE — CRITICAL
    ============================================================

    The user_code for "logic_bug" and "syntax_error" questions MUST NOT
    contain ANY comments that reveal the location or nature of bugs.

    ██████████████████████████████████████████████████████████████
    ██  ABSOLUTELY BANNED COMMENT PATTERNS IN user_code:       ██
    ██  - # BUG: ...    - # SYNTAX ERROR: ...                  ██
    ██  - # TYPO: ...   - # UNDEFINED: ...                     ██
    ██  - # FIX: ...    - # HINT: ...                          ██
    ██  - # ERROR: ...  - # WRONG: ...                         ██
    ██  - # should be   - # missing                            ██
    ██  Any comment that tells the user WHERE or WHAT the bug  ██
    ██  is defeats the entire purpose of the challenge!        ██
    ██████████████████████████████████████████████████████████████

    For "logic_bug": Code should have ONLY normal developer comments
    (e.g., # Initialize result, # Traverse the tree). The bug must
    be discoverable ONLY by running the tests and seeing wrong output.

    For "syntax_error": The errors ARE the challenge. Do NOT add
    comments pointing them out. The user should find them via the
    Python traceback when they run the code.

    ============================================================
    BULLETPROOF TEST GENERATION RULES
    ============================================================
    
    For ALL questions, follow these rules for sample_tests and comprehensive_tests:

    ████████████████████████████████████████████████████████████████████████████
    ██  NUCLEAR WARNING — DO NOT OUTPUT `class Solution` IN TEST SCRIPTS!  ██
    ████████████████████████████████████████████████████████████████████████████

    Test scripts are STITCHED AFTER user's code: full_code = user_code + tests.
    If your test script contains `class Solution:`, it OVERWRITES the user's
    real Solution class and every method returns None. ALL TESTS FAIL.
    Test scripts must assume Solution already exists. Only include: imports,
    helper classes (Node, TreeNode), helper functions, and the
    `if __name__ == '__main__':` block.
    
    1. Use HELPER FUNCTIONS to build data structures (no manual variable sprawl)
    2. Use DATA-DRIVEN test cases (simple Python lists/tuples)
    3. For trees/graphs: Include build_tree_from_edges() or build_graph() helper
    4. MANDATORY: Include compute_expected() reference function for validation
    5. Halt on first failure with exact format:
       "Wrong Answer: [passed] / [total] testcases passed"

    ANTI-HALLUCINATION RULES FOR EXPECTED VALUES:
    - NEVER hardcode expected values by guessing. Always compute them.
    - Use a compute_expected() reference function to calculate correct answers.
    - CONTRADICTION BAN: The SAME input MUST always produce the SAME expected output.
      If two test cases have identical inputs, they MUST have identical expected values.
    - For tree comparison: Sort children lists before comparing if order doesn't matter.
    - VERIFY each expected value by mentally tracing through the reference solution.
    
    ============================================================
    SAMPLE_TESTS FORMAT (MUST SHOW DETAILED OUTPUT)
    ============================================================
    
    The sample_tests MUST print detailed results for EACH test case like LeetCode.
    Use this EXACT template:
    
    ```python
    import sys
    from typing import List, Optional
    
    # Re-define any classes needed (Node, TreeNode, etc.)
    
    if __name__ == '__main__':
        solution = Solution()
        passed = 0
        total = 3
        
        # --- Test Case 1 ---
        input1 = [1, 2, 3]
        expected1 = 6
        try:
            actual1 = solution.methodName(input1)
        except Exception as e:
            print(f"Runtime Error: 0 / {{total}} testcases passed")
            print(f"Error: {{e}}")
            sys.exit(1)
        
        print("--- Test Case 1 ---")
        print(f"Input: {{input1}}")
        print(f"Expected: {{expected1}}")
        print(f"Actual: {{actual1}}")
        if actual1 == expected1:
            print("Status: PASS")
            passed += 1
        else:
            print("Status: FAIL")
        print()
        
        # --- Test Case 2 ---
        input2 = [5, 10]
        expected2 = 15
        try:
            actual2 = solution.methodName(input2)
        except Exception as e:
            print(f"Runtime Error: {{passed}} / {{total}} testcases passed")
            print(f"Error: {{e}}")
            sys.exit(1)
        
        print("--- Test Case 2 ---")
        print(f"Input: {{input2}}")
        print(f"Expected: {{expected2}}")
        print(f"Actual: {{actual2}}")
        if actual2 == expected2:
            print("Status: PASS")
            passed += 1
        else:
            print("Status: FAIL")
        print()
        
        # --- Test Case 3 ---
        input3 = [0]
        expected3 = 0
        try:
            actual3 = solution.methodName(input3)
        except Exception as e:
            print(f"Runtime Error: {{passed}} / {{total}} testcases passed")
            print(f"Error: {{e}}")
            sys.exit(1)
        
        print("--- Test Case 3 ---")
        print(f"Input: {{input3}}")
        print(f"Expected: {{expected3}}")
        print(f"Actual: {{actual3}}")
        if actual3 == expected3:
            print("Status: PASS")
            passed += 1
        else:
            print("Status: FAIL")
        print()
        
        # Summary
        print("=" * 30)
        print(f"Sample Tests: {{passed}}/{{total}} Passed")
        if passed == total:
            print("All sample tests passed!")
        print("=" * 30)
    ```
    
    CRITICAL: Each test case MUST print:
    - "--- Test Case N ---"
    - "Input: [the input value]"
    - "Expected: [the expected value]"
    - "Actual: [the actual value returned]"
    - "Status: PASS" or "Status: FAIL"

    ============================================================
    JSON SAFETY RULES FOR ALL STRING FIELDS
    ============================================================

    Your output is parsed by json.loads(). Broken JSON = total failure.

    RULE 1 — NO ASCII ART TREE DIAGRAMS in the "description" field.
    Tree diagrams use / \\ | characters which produce invalid JSON
    escape sequences and crash the parser. Instead of:
        ```
            1
           / | \\
          2  3  4
        ```
    Use a text-based representation:
        Tree: 1 -> [2, 3, 4], 2 -> [5, 6]
    Or describe the tree in words:
        "Root node 1 has children 2, 3, 4. Node 2 has children 5, 6."

    RULE 2 — NO BACKSLASH characters in "description", "title", or "hints".
    The only backslashes allowed in the JSON output are:
      \\n (newline), \\t (tab), \\\\ (literal backslash), \\" (escaped quote)
    Never write / \\ or | \\ or any raw backslash in prose text.

    RULE 3 — Test all \\n in your output. Every newline in a JSON string
    value MUST be written as \\n. Literal newlines break JSON.

    ============================================================
    OUTPUT JSON SCHEMA (EXACT FORMAT REQUIRED)
    ============================================================
    
    {{
        "topic": "Brief topic name extracted from content",
        "total_questions": 4,
        "estimated_time_minutes": 60,
        "questions": [
            {{
                "question_type": "scratch",
                "title": "Problem Title",
                "description": "## Problem Statement\\n...\\n## Examples\\n...\\n## Constraints\\n...",
                "difficulty": "Medium",
                "time_limit_minutes": 15,
                "user_code": "from typing import List\\n\\nclass Solution:\\n    def methodName(self, nums: List[int]) -> int:\\n        pass",
                "sample_tests": "import sys\\n# 3 sample test cases...",
                "comprehensive_tests": "import sys\\n# 20+ test cases with compute_expected()...",
                "hints": ["Hint 1 without solution", "Hint 2"],
                "tags": ["Array", "Hash Table"]
            }},
            {{
                "question_type": "logic_bug",
                "title": "Debug: Problem Title",
                "description": "## Problem Statement\\n...\\n\\n### Bug Report\\nThe following code is failing some test cases. Find and fix the bug(s).",
                "difficulty": "Medium",
                "time_limit_minutes": 10,
                "user_code": "from typing import List\\n\\nclass Solution:\\n    def methodName(self, nums: List[int]) -> int:\\n        result = 1\\n        for i in range(len(nums) - 1):\\n            result += nums[i]\\n        return result",
                "sample_tests": "import sys\\n# Tests that FAIL with buggy code...",
                "comprehensive_tests": "import sys\\n# Tests that expose the bug with compute_expected()...",
                "hints": ["Check initialization values", "Verify loop bounds"],
                "tags": ["Debugging", "Array"]
            }},
            {{
                "question_type": "syntax_error",
                "title": "Fix: Problem Title",
                "description": "## Problem Statement\\n...\\n\\n### Debug Report\\nThe following code has syntax errors and won't run. Fix all errors.",
                "difficulty": "Easy",
                "time_limit_minutes": 8,
                "user_code": "from typing import List\\n\\nclass Solution:\\n    def methodName(self, nums: List[int]) -> int\\n        reuslt = 0\\n        for i in range(len(nums))\\n            reuslt += nums[i]\\n        return result",
                "sample_tests": "import sys\\n# Tests for correct implementation...",
                "comprehensive_tests": "import sys\\n# Full test suite with compute_expected()...",
                "hints": ["Look for missing colons", "Check variable spelling"],
                "tags": ["Syntax", "Debugging"]
            }},
            {{
                "question_type": "optimization",
                "title": "Optimize: Problem Title",
                "description": "## Problem Statement\\n...\\n\\n### Performance Report\\nThe following O(N squared) solution times out on large inputs. Optimize to O(N).",
                "difficulty": "Hard",
                "time_limit_minutes": 20,
                "user_code": "from typing import List\\n\\nclass Solution:\\n    def methodName(self, nums: List[int], target: int) -> int:\\n        result = 0\\n        for i in range(len(nums)):\\n            for j in range(i + 1, len(nums)):\\n                if nums[i] + nums[j] == target:\\n                    result += 1\\n        return result",
                "sample_tests": "import sys\\n# Small tests that pass with brute force...",
                "comprehensive_tests": "import sys\\n# Include LARGE inputs that timeout with O(N squared)...",
                "hints": ["Consider using a hash map", "Can you solve in one pass?"],
                "tags": ["Optimization", "Hash Table", "Time Complexity"]
            }}
        ]
    }}

    ============================================================
    VALIDATION CHECKLIST
    ============================================================

    Before outputting, verify:
    [ ] Exactly 4 questions in the array
    [ ] question_type is exactly: "scratch", "logic_bug", "syntax_error", "optimization"
    [ ] "scratch" has user_code with ONLY `pass` - no implementation
    [ ] "logic_bug" has COMPLETE code with subtle LOGIC errors (runs but wrong output)
    [ ] "syntax_error" has COMPLETE code with SYNTAX errors (doesn't run)
    [ ] "optimization" has COMPLETE working code that is O(N squared) or worse
    [ ] All questions relate to the SAME TOPIC from the excerpt
    [ ] Each question has valid sample_tests and comprehensive_tests
    [ ] All test scripts use helper functions (no variable sprawl)
    [ ] All newlines escaped as \\n in JSON strings
    [ ] NO SPOILER COMMENTS in user_code (no # BUG:, # SYNTAX ERROR:, # TYPO:, etc.)
    [ ] comprehensive_tests uses compute_expected() - never hardcoded guesses
    [ ] No contradictory test cases (same input -> different expected)
    """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        raw_text = response.text.strip()
        print(f"Batch Response Length: {len(raw_text)} chars")

        # Clean markdown formatting
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        # Sanitize and parse JSON (with robust handling of malformed Gemini JSON)
        try:
            parsed_response = safe_json_loads(raw_text.strip())
        except json.JSONDecodeError as je:
            # Log detailed debug info about the parsing failure
            print(f"JSON Parsing Error in batch mode: {je}")
            print(f"Error at position {je.pos}, line {je.lineno}, column {je.colno}")
            # Show context around the error
            start = max(0, je.pos - 50)
            end = min(len(raw_text), je.pos + 50)
            print(f"Context around error: ...{repr(raw_text[start:end])}...")
            return get_fallback_batch_response()

        # Validate we got 4 questions
        if "questions" in parsed_response and len(parsed_response["questions"]) == 4:
            print(f"Successfully generated batch assessment with 4 questions")
            for i, q in enumerate(parsed_response["questions"]):
                print(f"   {i+1}. [{q.get('question_type', '?')}] {q.get('title', 'Untitled')}")
        else:
            print(f"Warning: Expected 4 questions, got {len(parsed_response.get('questions', []))}")

        parsed_response['assessment_mode'] = 'batch'

        # --- POST-PROCESSING: Strip spoiler comments from user_code ---
        # Safety net in case the LLM ignores the anti-spoiler prompt rule
        spoiler_pattern = re.compile(
            r'#\s*(?:BUG|BUGGY|SYNTAX\s*ERROR|TYPO|UNDEFINED|FIX|HINT|ERROR|WRONG'
            r'|should\s+be|missing|incorrect|todo|HACK|FIXME|NOTE:.*bug|NOTE:.*error'
            r'|BRUTE\s*FORCE).*$',
            re.IGNORECASE | re.MULTILINE
        )
        if "questions" in parsed_response:
            for q in parsed_response["questions"]:
                if "user_code" in q and q.get("question_type") in ("logic_bug", "syntax_error"):
                    original = q["user_code"]
                    cleaned = spoiler_pattern.sub('', original)
                    # Remove any trailing whitespace on lines where we stripped comments
                    cleaned = re.sub(r'[ \t]+$', '', cleaned, flags=re.MULTILINE)
                    if cleaned != original:
                        print(f"[SPOILER STRIP] Removed spoiler comments from {q.get('question_type')} question")
                    q["user_code"] = cleaned

        # --- POST-PROCESSING: Ensure imports exist in all code fields ---
        if "questions" in parsed_response:
            for idx, q in enumerate(parsed_response["questions"]):
                # Ensure all required string fields exist (prevent None/missing)
                for field in ['user_code', 'sample_tests', 'comprehensive_tests',
                              'title', 'description', 'question_type', 'difficulty']:
                    if field not in q or q[field] is None:
                        q[field] = q.get(field, '') or ''
                        print(f"[VALIDATION] Q{idx+1}: Set missing '{field}' to empty string")

                for field in ['hints', 'tags']:
                    if field not in q or not isinstance(q.get(field), list):
                        q[field] = q.get(field, []) or []

                if 'time_limit_minutes' not in q or not isinstance(q.get('time_limit_minutes'), int):
                    q['time_limit_minutes'] = 12  # safe default

                if "user_code" in q and q["user_code"]:
                    q["user_code"] = _ensure_imports_in_code(q["user_code"])
                if "sample_tests" in q and q["sample_tests"]:
                    # Strip any duplicate Solution class from test scripts
                    q["sample_tests"] = _strip_solution_class_from_tests(q["sample_tests"])
                    q["sample_tests"] = _ensure_imports_in_code(q["sample_tests"], is_test=True)
                    q["sample_tests"] = _ensure_node_class_in_tests(
                        q.get("user_code", ""), q["sample_tests"]
                    )
                if "comprehensive_tests" in q and q["comprehensive_tests"]:
                    # Strip any duplicate Solution class from test scripts
                    q["comprehensive_tests"] = _strip_solution_class_from_tests(q["comprehensive_tests"])
                    q["comprehensive_tests"] = _ensure_imports_in_code(q["comprehensive_tests"], is_test=True)
                    q["comprehensive_tests"] = _ensure_node_class_in_tests(
                        q.get("user_code", ""), q["comprehensive_tests"]
                    )

        return parsed_response

    except Exception as e:
        print(f"Batch Generation Error: {type(e).__name__}: {e}")
        return get_fallback_batch_response()


def get_fallback_batch_response() -> dict:
    """Fallback response for batch mode when Gemini fails."""
    print("WARNING: Returning FALLBACK batch response")
    return {
        "topic": "Array Operations",
        "total_questions": 4,
        "estimated_time_minutes": 45,
        "assessment_mode": "batch",
        "is_fallback": True,
        "questions": [
            {
                "question_type": "scratch",
                "title": "Array Sum",
                "description": """## Problem Statement
Implement a function that calculates the sum of all elements in an array.

## Examples
**Example 1:**
Input: nums = [1, 2, 3]
Output: 6

**Example 2:**
Input: nums = [-1, 0, 1]
Output: 0

## Constraints
- 1 <= nums.length <= 10^4
- -10^6 <= nums[i] <= 10^6""",
                "difficulty": "Easy",
                "time_limit_minutes": 10,
                "user_code": """from typing import List

class Solution:
    def arraySum(self, nums: List[int]) -> int:
        \"\"\"Calculate the sum of all elements.\"\"\"
        pass""",
                "sample_tests": """import sys
from typing import List

if __name__ == '__main__':
    solution = Solution()
    passed = 0
    total = 3
    
    # --- Test Case 1 ---
    input1 = [1, 2, 3]
    expected1 = 6
    try:
        actual1 = solution.arraySum(input1)
    except Exception as e:
        print(f"Runtime Error: 0 / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 1 ---")
    print(f"Input: {input1}")
    print(f"Expected: {expected1}")
    print(f"Actual: {actual1}")
    if actual1 == expected1:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Test Case 2 ---
    input2 = [0]
    expected2 = 0
    try:
        actual2 = solution.arraySum(input2)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 2 ---")
    print(f"Input: {input2}")
    print(f"Expected: {expected2}")
    print(f"Actual: {actual2}")
    if actual2 == expected2:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Test Case 3 ---
    input3 = [-1, 1]
    expected3 = 0
    try:
        actual3 = solution.arraySum(input3)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 3 ---")
    print(f"Input: {input3}")
    print(f"Expected: {expected3}")
    print(f"Actual: {actual3}")
    if actual3 == expected3:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    print("=" * 30)
    print(f"Sample Tests: {passed}/{total} Passed")
    if passed == total:
        print("All sample tests passed!")
    print("=" * 30)
""",
                "comprehensive_tests": """import sys
if __name__ == '__main__':
    solution = Solution()
    tests = [([1,2,3], 6), ([0], 0), ([-1,1], 0), ([100], 100), (list(range(100)), 4950)]
    for i, (inp, exp) in enumerate(tests):
        act = solution.arraySum(inp)
        if act != exp:
            print(f"Wrong Answer: {i}/{len(tests)} passed"); sys.exit(0)
    print(f"Accepted: {len(tests)}/{len(tests)} passed")""",
                "hints": ["Consider iterating through the array", "What should you return for empty array?"],
                "tags": ["Array", "Math"]
            },
            {
                "question_type": "logic_bug",
                "title": "Debug: Array Sum",
                "description": """## Problem Statement
Calculate the sum of all elements in an array.

### Bug Report
The following code is failing some test cases. Find and fix the bug(s).

## Examples
**Example 1:**
Input: nums = [1, 2, 3]
Output: 6""",
                "difficulty": "Easy",
                "time_limit_minutes": 8,
                "user_code": """from typing import List

class Solution:
    def arraySum(self, nums: List[int]) -> int:
        \"\"\"Calculate the sum - CONTAINS BUGS!\"\"\"
        total = 1  # BUG: Should be 0
        for i in range(len(nums) - 1):  # BUG: Should be len(nums)
            total += nums[i]
        return total""",
                "sample_tests": """import sys
from typing import List

if __name__ == '__main__':
    solution = Solution()
    passed = 0
    total = 3

    # --- Test Case 1 ---
    input1 = [1, 2, 3]
    expected1 = 6
    try:
        actual1 = solution.arraySum(input1)
    except Exception as e:
        print(f"Runtime Error: 0 / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 1 ---")
    print(f"Input: {input1}")
    print(f"Expected: {expected1}")
    print(f"Actual: {actual1}")
    if actual1 == expected1:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Test Case 2 ---
    input2 = [5]
    expected2 = 5
    try:
        actual2 = solution.arraySum(input2)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 2 ---")
    print(f"Input: {input2}")
    print(f"Expected: {expected2}")
    print(f"Actual: {actual2}")
    if actual2 == expected2:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Test Case 3 ---
    input3 = [0, 0, 0]
    expected3 = 0
    try:
        actual3 = solution.arraySum(input3)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 3 ---")
    print(f"Input: {input3}")
    print(f"Expected: {expected3}")
    print(f"Actual: {actual3}")
    if actual3 == expected3:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    print("=" * 30)
    print(f"Sample Tests: {passed}/{total} Passed")
    if passed == total:
        print("All sample tests passed!")
    print("=" * 30)
""",
                "comprehensive_tests": """import sys
if __name__ == '__main__':
    solution = Solution()
    tests = [([1,2,3], 6), ([5], 5), ([0,0,0], 0), ([1], 1), ([-1,-2], -3)]
    for i, (inp, exp) in enumerate(tests):
        act = solution.arraySum(inp)
        if act != exp:
            print(f"Wrong Answer: {i}/{len(tests)} passed"); sys.exit(0)
    print(f"Accepted: {len(tests)}/{len(tests)} passed")""",
                "hints": ["Check the initial value of total", "Does the loop cover all elements?"],
                "tags": ["Debugging", "Array"]
            },
            {
                "question_type": "syntax_error",
                "title": "Fix: Array Sum",
                "description": """## Problem Statement
Calculate the sum of all elements in an array.

### Debug Report
The following code has syntax errors and won't run. Fix all errors to make it work.""",
                "difficulty": "Easy",
                "time_limit_minutes": 5,
                "user_code": """from typing import List

class Solution:
    def arraySum(self, nums: List[int]) -> int
        \"\"\"Calculate the sum - FIX SYNTAX ERRORS!\"\"\"
        totla = 0
        for i in range(len(nums))
            total += nums[i]
        return total""",
                "sample_tests": """import sys
from typing import List

if __name__ == '__main__':
    solution = Solution()
    passed = 0
    total = 3

    # --- Test Case 1 ---
    input1 = [1, 2, 3]
    expected1 = 6
    try:
        actual1 = solution.arraySum(input1)
    except Exception as e:
        print(f"Runtime Error: 0 / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 1 ---")
    print(f"Input: {input1}")
    print(f"Expected: {expected1}")
    print(f"Actual: {actual1}")
    if actual1 == expected1:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Test Case 2 ---
    input2 = [0]
    expected2 = 0
    try:
        actual2 = solution.arraySum(input2)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 2 ---")
    print(f"Input: {input2}")
    print(f"Expected: {expected2}")
    print(f"Actual: {actual2}")
    if actual2 == expected2:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Test Case 3 ---
    input3 = [1, 1, 1]
    expected3 = 3
    try:
        actual3 = solution.arraySum(input3)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 3 ---")
    print(f"Input: {input3}")
    print(f"Expected: {expected3}")
    print(f"Actual: {actual3}")
    if actual3 == expected3:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    print("=" * 30)
    print(f"Sample Tests: {passed}/{total} Passed")
    if passed == total:
        print("All sample tests passed!")
    print("=" * 30)
""",
                "comprehensive_tests": """import sys
if __name__ == '__main__':
    solution = Solution()
    tests = [([1,2,3], 6), ([0], 0), ([1,1,1], 3)]
    for i, (inp, exp) in enumerate(tests):
        act = solution.arraySum(inp)
        if act != exp:
            print(f"Wrong Answer: {i}/{len(tests)} passed"); sys.exit(0)
    print(f"Accepted: {len(tests)}/{len(tests)} passed")""",
                "hints": ["Look for missing colons", "Check variable name spelling"],
                "tags": ["Syntax", "Debugging"]
            },
            {
                "question_type": "optimization",
                "title": "Optimize: Two Sum Count",
                "description": """## Problem Statement
Count pairs in array that sum to target.

### Performance Report
The current O(N²) solution times out on large inputs. Optimize to O(N).

## Examples
**Example 1:**
Input: nums = [1, 2, 3, 4], target = 5
Output: 2 (pairs: (1,4), (2,3))""",
                "difficulty": "Medium",
                "time_limit_minutes": 15,
                "user_code": """from typing import List

class Solution:
    def twoSumCount(self, nums: List[int], target: int) -> int:
        \"\"\"Count pairs summing to target - OPTIMIZE THIS O(N²) CODE!\"\"\"
        count = 0
        # Brute force O(N²) - make this O(N)!
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                if nums[i] + nums[j] == target:
                    count += 1
        return count""",
                "sample_tests": """import sys
from typing import List

if __name__ == '__main__':
    solution = Solution()
    passed = 0
    total = 3

    # --- Test Case 1 ---
    input1 = ([1, 2, 3, 4], 5)
    expected1 = 2
    try:
        actual1 = solution.twoSumCount(*input1)
    except Exception as e:
        print(f"Runtime Error: 0 / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 1 ---")
    print(f"Input: nums={input1[0]}, target={input1[1]}")
    print(f"Expected: {expected1}")
    print(f"Actual: {actual1}")
    if actual1 == expected1:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Test Case 2 ---
    input2 = ([1, 1, 1], 2)
    expected2 = 3
    try:
        actual2 = solution.twoSumCount(*input2)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 2 ---")
    print(f"Input: nums={input2[0]}, target={input2[1]}")
    print(f"Expected: {expected2}")
    print(f"Actual: {actual2}")
    if actual2 == expected2:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Test Case 3 ---
    input3 = ([0, 0, 0, 0], 0)
    expected3 = 6
    try:
        actual3 = solution.twoSumCount(*input3)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error: {e}")
        sys.exit(1)

    print("--- Test Case 3 ---")
    print(f"Input: nums={input3[0]}, target={input3[1]}")
    print(f"Expected: {expected3}")
    print(f"Actual: {actual3}")
    if actual3 == expected3:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    print("=" * 30)
    print(f"Sample Tests: {passed}/{total} Passed")
    if passed == total:
        print("All sample tests passed!")
    print("=" * 30)
""",
                "comprehensive_tests": """import sys
if __name__ == '__main__':
    solution = Solution()
    tests = [(([1,2,3,4], 5), 2), (([1,1,1], 2), 3), ((list(range(1000)), 999), 499)]
    for i, (inp, exp) in enumerate(tests):
        act = solution.twoSumCount(*inp)
        if act != exp:
            print(f"Wrong Answer: {i}/{len(tests)} passed"); sys.exit(0)
    print(f"Accepted: {len(tests)}/{len(tests)} passed")""",
                "hints": ["Use a hash map to store seen values", "Can you count in one pass?"],
                "tags": ["Optimization", "Hash Table"]
            }
        ]
    }


def get_fallback_response() -> dict:
    """Generate a fallback response when Gemini fails - includes all proper imports."""
    print("WARNING: Returning FALLBACK response - Gemini API call failed!")
    return {
        "category": "General Technical Document",
        "confidence": "Medium (70%)",
        "summary": """## Problem Statement
Implement a function that calculates the sum of all elements in an array.

## Examples
**Example 1:**
Input: nums = [1, 2, 3]
Output: 6
Explanation: 1 + 2 + 3 = 6

**Example 2:**
Input: nums = [-1, 0, 1]
Output: 0

## Constraints
- 1 <= nums.length <= 10^4
- -10^6 <= nums[i] <= 10^6""",
        "key_metrics": {"complexity": "O(N)", "type": "Array", "difficulty": "Easy"},
        "insights": ["Consider all elements", "Handle edge cases", "Think about efficiency"],
        "recommendations": ["Practice array problems", "Study iteration patterns"],
        "is_fallback": True,  # Flag to identify fallback response
        "user_code": """from typing import List, Optional, Dict, Set, Tuple

class Solution:
    def arraySum(self, nums: List[int]) -> int:
        \"\"\"
        Calculate the sum of all elements in the array.

        Args:
            nums: List of integers

        Returns:
            The sum of all elements as an integer
        \"\"\"
        pass""",
        "sample_tests": """import sys
from typing import List, Optional, Dict, Set, Tuple

if __name__ == '__main__':
    solution = Solution()
    passed = 0
    total = 3

    # --- Sample Test 1 ---
    input1 = [1, 2, 3]
    expected1 = 6
    try:
        actual1 = solution.arraySum(input1)
    except Exception as e:
        print(f"Runtime Error: 0 / {total} testcases passed")
        print(f"Error Message: {e}")
        sys.exit(1)

    print("--- Sample Test 1 ---")
    print(f"Input: nums = {input1}")
    print(f"Expected: {expected1}")
    print(f"Actual: {actual1}")
    if actual1 == expected1:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Sample Test 2 ---
    input2 = [-1, 0, 1]
    expected2 = 0
    try:
        actual2 = solution.arraySum(input2)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error Message: {e}")
        sys.exit(1)
    
    print("--- Sample Test 2 ---")
    print(f"Input: nums = {input2}")
    print(f"Expected: {expected2}")
    print(f"Actual: {actual2}")
    if actual2 == expected2:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()
    
    # --- Sample Test 3 ---
    input3 = [100]
    expected3 = 100
    try:
        actual3 = solution.arraySum(input3)
    except Exception as e:
        print(f"Runtime Error: {passed} / {total} testcases passed")
        print(f"Error Message: {e}")
        sys.exit(1)
    
    print("--- Sample Test 3 ---")
    print(f"Input: nums = {input3}")
    print(f"Expected: {expected3}")
    print(f"Actual: {actual3}")
    if actual3 == expected3:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()
    
    print("=" * 30)
    print(f"Sample Tests: {passed}/{total} Passed")
    print("=" * 30)
""",
        "comprehensive_tests": """import sys
from typing import List, Optional, Dict, Set, Tuple

if __name__ == '__main__':
    solution = Solution()
    
    test_cases = [
        {"input": [1, 2, 3], "expected": 6},
        {"input": [0], "expected": 0},
        {"input": [-1, 1], "expected": 0},
        {"input": [100, -50, 25], "expected": 75},
        {"input": [], "expected": 0},
        {"input": [1], "expected": 1},
        {"input": [-1], "expected": -1},
        {"input": [0, 0, 0], "expected": 0},
        {"input": [1, 1, 1, 1, 1], "expected": 5},
        {"input": [-1, -2, -3], "expected": -6},
        {"input": [1000000, -1000000], "expected": 0},
        {"input": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "expected": 55},
        {"input": [-5, 5, -10, 10, -15, 15], "expected": 0},
        {"input": [999999], "expected": 999999},
        {"input": [-999999], "expected": -999999},
        {"input": [1, -1, 2, -2, 3, -3, 4, -4, 5, -5], "expected": 0},
        {"input": [100, 200, 300, 400, 500], "expected": 1500},
        {"input": [1] * 100, "expected": 100},
        {"input": list(range(1, 101)), "expected": 5050},
        {"input": list(range(-50, 51)), "expected": 0},
        {"input": [i for i in range(1, 51)], "expected": 1275},
        {"input": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100], "expected": 550},
        {"input": [-100, -200, -300], "expected": -600},
        {"input": [0, 1, 0, 1, 0, 1], "expected": 3},
        {"input": [5, -5, 10, -10, 15, -15, 20, -20], "expected": 0},
        {"input": [123, 456, 789], "expected": 1368},
        {"input": [1, 2], "expected": 3},
        {"input": [2, 3], "expected": 5},
        {"input": [3, 4], "expected": 7},
        {"input": [4, 5], "expected": 9},
        {"input": [5, 6], "expected": 11},
        {"input": [6, 7], "expected": 13},
        {"input": [7, 8], "expected": 15},
        {"input": [8, 9], "expected": 17},
        {"input": [9, 10], "expected": 19},
        {"input": [10, 11], "expected": 21},
        {"input": [1, 2, 3, 4], "expected": 10},
        {"input": [5, 10, 15, 20, 25], "expected": 75},
        {"input": [-1, -1, -1, -1], "expected": -4},
        {"input": [50, 50, 50, 50], "expected": 200},
        {"input": [1, -2, 3, -4, 5, -6, 7], "expected": 4},
        {"input": [0, 0, 0, 0, 0, 0, 0, 0, 0, 1], "expected": 1},
        {"input": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0], "expected": 1},
        {"input": list(range(1, 1001)), "expected": 500500},
        {"input": [i * -1 for i in range(1, 101)], "expected": -5050},
        {"input": [42], "expected": 42},
        {"input": [7, 14, 21, 28, 35], "expected": 105},
        {"input": [11, 22, 33, 44, 55, 66, 77, 88, 99], "expected": 495},
        {"input": [1, 3, 5, 7, 9, 11, 13, 15, 17, 19], "expected": 100},
        {"input": [2, 4, 6, 8, 10, 12, 14, 16, 18, 20], "expected": 110},
    ]
    
    total = len(test_cases)
    for i, tc in enumerate(test_cases):
        try:
            actual = solution.arraySum(tc["input"])
        except Exception as e:
            print(f"Runtime Error: {i} / {total} testcases passed")
            print()
            print(f"Error Message: {e}")
            sys.exit(1)
        
        if actual != tc["expected"]:
            print(f"Wrong Answer: {i} / {total} testcases passed")
            print()
            print(f"Input:")
            print(f"{tc['input']}")
            print()
            print(f"Output:")
            print(f"{actual}")
            print()
            print(f"Expected:")
            print(f"{tc['expected']}")
            sys.exit(0)
    
    print(f"Accepted: {total}/{total} testcases passed")
"""
    }


@app.post("/analyze-doc")
async def analyze_document(file: UploadFile = File(...)):
    """
    CORE IDP ENDPOINT - PDF/Text Analysis with Caching
    Accepts PDF or text files, extracts content, and performs AI-powered analysis.
    Uses in-memory caching to avoid redundant API calls.
    """
    print(f"Analyzing document: {file.filename}")

    # Read file content
    content = await file.read()

    # Determine file type and extract text
    if file.filename.lower().endswith('.pdf'):
        text_content = extract_text_from_pdf(content)
        source_type = "PDF Document"
    else:
        try:
            text_content = content.decode("utf-8")
            source_type = "Text File"
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or text files.")

    print(f"Extracted {len(text_content)} characters from {source_type}")

    # CACHING: Check if we've already processed this content
    cache_key = get_cache_key_for_text(text_content)
    cached_response = get_cached_response(cache_key)
    if cached_response:
        return cached_response

    # Perform AI analysis (cache miss)
    analysis = analyze_with_gemini(text_content, source_type)

    # IMPORTANT: Only cache successful responses, NOT fallback responses
    if not analysis.get('is_fallback', False):
        cache_response(cache_key, analysis)
    else:
        print("NOT caching fallback response - will retry on next request")

    return analysis


@app.post("/analyze-url")
async def analyze_url(payload: URLPayload):
    """
    URL ANALYSIS ENDPOINT with Caching
    Scrapes a URL and generates a 4-question assessment:
    1. Scratch - Write from scratch
    2. Logic Bug - Fix logic errors
    3. Syntax Error - Fix syntax errors
    4. Optimization - Optimize brute force
    """
    print(f"Analyzing URL: {payload.url}")

    # CACHING: Use URL as cache key
    cache_key = f"batch:{payload.url}"
    cached_response = get_cached_response(cache_key)
    if cached_response:
        return cached_response

    # Extract text from URL (cache miss)
    try:
        text_content = extract_text_from_url(payload.url)
        print(f"Extracted {len(text_content)} characters from URL")
        print(f"First 500 chars of extracted text: {text_content[:500]}")
    except Exception as e:
        print(f"URL Extraction Error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to extract content from URL: {str(e)}")

    # Always generate 4 question types
    print(f"Generating 4-question assessment...")
    analysis = generate_batch_assessment(text_content, f"Web URL: {payload.url}")

    # Log what we got back
    print(f"Assessment topic: {analysis.get('topic', 'UNKNOWN')}")
    print(f"Questions generated: {len(analysis.get('questions', []))}")
    print(f"Is fallback response: {analysis.get('is_fallback', False)}")

    # IMPORTANT: Only cache successful responses, NOT fallback responses
    if not analysis.get('is_fallback', False):
        cache_response(cache_key, analysis)
    else:
        print("NOT caching fallback response - will retry on next request")

    return analysis


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "OmniParse AI",
        "version": "2.0.0",
        "cache_size": len(SCENARIO_CACHE),
        "capabilities": ["PDF Analysis", "URL Scraping", "Code Generation", "AI Classification", "In-Memory Caching"]
    }


@app.get("/cache-stats")
def cache_stats():
    """Get cache statistics for monitoring."""
    return {
        "total_cached_scenarios": len(SCENARIO_CACHE),
        "cached_keys": list(SCENARIO_CACHE.keys())[:10],  # Show first 10 keys
        "memory_hint": "In-memory cache - clears on server restart"
    }


@app.post("/cache-clear")
def clear_cache():
    """Clear the entire cache (admin endpoint)."""
    global SCENARIO_CACHE
    count = len(SCENARIO_CACHE)
    SCENARIO_CACHE = {}
    print(f"Cache cleared: {count} entries removed")
    return {"status": "success", "cleared_entries": count}