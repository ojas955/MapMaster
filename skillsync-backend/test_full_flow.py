"""
Full end-to-end test for the CodingSkills pipeline.

Tests:
1. /api/coding/analyze-url -- URL extraction + Gemini batch assessment generation
2. /api/coding/execute -- Code execution with sample tests
3. /api/coding/execute -- Code execution with comprehensive tests (submit mode)
4. /api/coding/batch-submit -- AI evaluation of batch submissions

Uses: https://www.geeksforgeeks.org/dsa/binary-search-tree-data-structure/
"""

import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
# Force UTF-8 for stdout/stderr on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests
import json
import traceback

BASE_URL = "http://localhost:8000/api/coding"
TEST_URL = "https://www.geeksforgeeks.org/dsa/binary-search-tree-data-structure/"

def separator(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def test_analyze_url():
    """Test 1: Analyze URL and get batch questions."""
    separator("TEST 1: /analyze-url")

    try:
        r = requests.post(f"{BASE_URL}/analyze-url",
                         json={"url": TEST_URL},
                         timeout=180)
    except Exception as e:
        print(f"FAIL: Request error: {e}")
        return None

    print(f"Status Code: {r.status_code}")

    if r.status_code != 200:
        print(f"FAIL: Non-200 status code")
        print(f"Response: {r.text[:2000]}")
        return None

    try:
        data = r.json()
    except json.JSONDecodeError as e:
        print(f"FAIL: JSON decode error: {e}")
        print(f"Raw response (first 2000 chars): {r.text[:2000]}")
        return None

    # Validate structure
    print(f"Response keys: {list(data.keys())}")
    print(f"Topic: {data.get('topic', 'MISSING')}")
    print(f"Is Fallback: {data.get('is_fallback', False)}")
    print(f"Assessment mode: {data.get('assessment_mode', 'MISSING')}")

    questions = data.get("questions", [])
    print(f"Number of questions: {len(questions)}")

    if len(questions) != 4:
        print(f"WARNING: Expected 4 questions, got {len(questions)}")

    errors = []
    for i, q in enumerate(questions):
        print(f"\n--- Question {i+1}: {q.get('question_type', 'MISSING TYPE')} ---")
        print(f"  Title: {q.get('title', 'MISSING')}")
        print(f"  Difficulty: {q.get('difficulty', 'MISSING')}")
        print(f"  Time Limit: {q.get('time_limit_minutes', 'MISSING')} min")
        print(f"  User Code length: {len(q.get('user_code', ''))}")
        print(f"  Sample Tests length: {len(q.get('sample_tests', ''))}")
        print(f"  Comprehensive Tests length: {len(q.get('comprehensive_tests', ''))}")
        print(f"  Hints: {q.get('hints', [])}")
        print(f"  Tags: {q.get('tags', [])}")

        # Validate required fields
        required_fields = ['question_type', 'title', 'description', 'difficulty',
                          'time_limit_minutes', 'user_code', 'sample_tests',
                          'comprehensive_tests', 'hints', 'tags']
        for field in required_fields:
            if field not in q or not q[field]:
                errors.append(f"Q{i+1}: Missing or empty '{field}'")

        # Check that user_code is valid Python (at least parseable)
        user_code = q.get('user_code', '')
        if user_code:
            # Check for double-escaped newlines
            if '\\n' in user_code and '\n' not in user_code:
                errors.append(f"Q{i+1}: user_code has double-escaped newlines (\\\\n instead of \\n)")
                print(f"  WARNING: user_code appears to have double-escaped newlines!")
                print(f"  First 200 chars: {repr(user_code[:200])}")
            else:
                try:
                    compile(user_code, f"<Q{i+1}_user_code>", "exec")
                    print(f"  User Code: COMPILES OK")
                except SyntaxError as e:
                    if q.get('question_type') == 'syntax_error':
                        print(f"  User Code: Has syntax errors (expected for syntax_error type)")
                    else:
                        errors.append(f"Q{i+1}: user_code has unexpected SyntaxError: {e}")
                        print(f"  WARNING: user_code SyntaxError: {e}")

        # Check that tests reference Solution class
        sample_tests = q.get('sample_tests', '')
        if sample_tests and 'Solution' not in sample_tests:
            print(f"  WARNING: sample_tests doesn't reference 'Solution' class")
            errors.append(f"Q{i+1}: sample_tests missing 'Solution' reference")

    if errors:
        print(f"\nERRORS FOUND:")
        for e in errors:
            print(f"  ❌ {e}")
    else:
        print(f"\n✅ All validation checks passed!")

    print(f"\nTest 1 Result: {'PASS' if not errors else 'FAIL'}")
    return data


def test_execute_code(questions_data):
    """Test 2: Execute code for each question type."""
    separator("TEST 2: /execute (Run Code)")

    if not questions_data:
        print("SKIP: No questions data from Test 1")
        return

    questions = questions_data.get("questions", [])
    if not questions:
        print("SKIP: No questions available")
        return

    results = {}
    for i, q in enumerate(questions):
        print(f"\n--- Run Code: Q{i+1} [{q['question_type']}] ---")

        payload = {
            "code": q["user_code"],
            "sample_tests": q.get("sample_tests", ""),
            "comprehensive_tests": q.get("comprehensive_tests", ""),
            "is_submit": False
        }

        try:
            r = requests.post(f"{BASE_URL}/execute", json=payload, timeout=30)
        except Exception as e:
            print(f"FAIL: Request error: {e}")
            results[i] = "ERROR"
            continue

        print(f"  Status: {r.status_code}")

        if r.status_code != 200:
            print(f"  FAIL: Non-200 status")
            print(f"  Body: {r.text[:500]}")
            results[i] = "ERROR"
            continue

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            print(f"  FAIL: JSON decode error: {e}")
            results[i] = "JSON_ERROR"
            continue

        stdout = data.get("stdout", "")
        stderr = data.get("stderr", "")

        print(f"  stdout length: {len(stdout)}")
        print(f"  stderr length: {len(stderr)}")

        if stderr:
            print(f"  STDERR (first 500 chars): {stderr[:500]}")

        if stdout:
            print(f"  STDOUT (first 500 chars): {stdout[:500]}")

        # For 'scratch' type with 'pass', we expect some error or "No output"
        if q['question_type'] == 'scratch':
            print(f"  NOTE: scratch question with 'pass' - errors are expected")

        results[i] = data

    print(f"\nTest 2 Result: DONE (individual results logged above)")
    return results


def test_submit_code(questions_data):
    """Test 3: Submit code (comprehensive tests) for each question."""
    separator("TEST 3: /execute (Submit Mode)")

    if not questions_data:
        print("SKIP: No questions data from Test 1")
        return

    questions = questions_data.get("questions", [])
    if not questions:
        print("SKIP: No questions available")
        return

    # Only test with Q1 to save time
    q = questions[0]
    print(f"\n--- Submit Code: Q1 [{q['question_type']}] ---")

    payload = {
        "code": q["user_code"],
        "sample_tests": q.get("sample_tests", ""),
        "comprehensive_tests": q.get("comprehensive_tests", ""),
        "is_submit": True
    }

    try:
        r = requests.post(f"{BASE_URL}/execute", json=payload, timeout=60)
    except Exception as e:
        print(f"FAIL: Request error: {e}")
        return

    print(f"  Status: {r.status_code}")

    if r.status_code != 200:
        print(f"  FAIL: Non-200 status")
        print(f"  Body: {r.text[:500]}")
        return

    try:
        data = r.json()
        print(f"  stdout: {data.get('stdout', '')[:500]}")
        print(f"  stderr: {data.get('stderr', '')[:500]}")
        print(f"\nTest 3 Result: PASS")
    except json.JSONDecodeError as e:
        print(f"  FAIL: JSON decode error: {e}")


def test_batch_submit(questions_data):
    """Test 4: Batch evaluate all questions."""
    separator("TEST 4: /batch-submit")

    if not questions_data:
        print("SKIP: No questions data from Test 1")
        return

    questions = questions_data.get("questions", [])
    if not questions:
        print("SKIP: No questions available")
        return

    # Build a batch payload with minimal data
    batch_payload = {
        "questions": [
            {
                "question_type": q.get("question_type", "scratch"),
                "title": q.get("title", "Unknown"),
                "code": q.get("user_code", "pass"),
                "attempts": 2,
                "logs": [
                    {"attempt": 1, "log": "Test error log for testing"}
                ]
            }
            for q in questions
        ],
        "tab_switches": 1,
        "paste_count": 0,
        "proctoring_data": {
            "face_present_pct": 95,
            "face_absent_count": 1,
            "multiple_faces_count": 0,
            "gaze_away_count": 2,
            "gaze_away_pct": 5,
            "objects_detected": [],
            "object_violation_count": 0,
            "violations": [],
            "total_violations": 0,
            "duration_seconds": 600,
            "expression_summary": {"dominant": "neutral", "distribution": {"neutral": 80, "happy": 20}},
            "confidence_score": 85,
            "integrity_score": 90
        },
        "time_taken_seconds": 600
    }

    try:
        r = requests.post(f"{BASE_URL}/batch-submit", json=batch_payload, timeout=120)
    except Exception as e:
        print(f"FAIL: Request error: {e}")
        return

    print(f"Status Code: {r.status_code}")

    if r.status_code != 200:
        print(f"FAIL: Non-200 status")
        print(f"Response: {r.text[:2000]}")
        return

    try:
        data = r.json()
    except json.JSONDecodeError as e:
        print(f"FAIL: JSON decode error: {e}")
        print(f"Raw: {r.text[:2000]}")
        return

    print(f"Response keys: {list(data.keys())}")
    print(f"Logic Score: {data.get('logic_score', 'MISSING')}")
    print(f"Resilience Score: {data.get('resilience_score', 'MISSING')}")
    print(f"Clean Code Score: {data.get('clean_code_score', 'MISSING')}")
    print(f"Debugging Score: {data.get('debugging_score', 'MISSING')}")
    print(f"Originality Score: {data.get('originality_score', 'MISSING')}")
    print(f"Executive Summary: {data.get('executive_summary', 'MISSING')[:300]}")

    required_keys = ['logic_score', 'resilience_score', 'clean_code_score',
                     'debugging_score', 'originality_score', 'executive_summary']
    missing = [k for k in required_keys if k not in data]
    if missing:
        print(f"FAIL: Missing keys: {missing}")
    else:
        print(f"\n✅ All required result keys present")

    # Validate scores are numbers
    for key in ['logic_score', 'resilience_score', 'clean_code_score',
                'debugging_score', 'originality_score']:
        val = data.get(key)
        if val is not None and not isinstance(val, (int, float)):
            print(f"WARNING: {key} is not a number: {type(val)} = {val}")

    print(f"\nTest 4 Result: {'PASS' if not missing else 'FAIL'}")
    return data


if __name__ == "__main__":
    print("Starting Full CodingSkills Pipeline Test")
    print(f"Target URL: {TEST_URL}")
    print(f"API Base: {BASE_URL}")

    # Test 1: Analyze URL
    try:
        questions_data = test_analyze_url()
    except Exception as e:
        print(f"TEST 1 EXCEPTION: {e}")
        traceback.print_exc()
        questions_data = None

    # Test 2: Execute code (run mode)
    try:
        test_execute_code(questions_data)
    except Exception as e:
        print(f"TEST 2 EXCEPTION: {e}")
        traceback.print_exc()

    # Test 3: Execute code (submit mode)
    try:
        test_submit_code(questions_data)
    except Exception as e:
        print(f"TEST 3 EXCEPTION: {e}")
        traceback.print_exc()

    # Test 4: Batch submit
    try:
        test_batch_submit(questions_data)
    except Exception as e:
        print(f"TEST 4 EXCEPTION: {e}")
        traceback.print_exc()

    separator("TEST COMPLETE")
