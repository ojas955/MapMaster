"""
JPlag Integration Module for SkillSync
=======================================

Wraps the open-source JPlag Java application (https://github.com/jplag/JPlag)
for token-based code plagiarism detection via subprocess.

JPlag is a scientifically published tool that tokenizes source code at the
language-grammar level and uses a greedy string tiling algorithm (Running
Karp-Rabin) to find matching token subsequences. It catches:
  - Variable/function renaming
  - Whitespace and formatting changes
  - Comment modifications
  - Statement reordering
  - Code insertion (dead code padding)

This module handles:
  1. Directory scaffolding (base code + per-user submission folders)
  2. Subprocess invocation of `java -jar jplag.jar`
  3. Parsing the results ZIP (overview.json) for pairwise similarity scores
  4. Cleanup of all temporary files

Requires:
  - Java 17+ on the system PATH
  - jplag.jar in the backend directory (downloaded from GitHub Releases)
"""

import os
import json
import shutil
import subprocess
import tempfile
import zipfile
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field


# ============================================================
# CONFIGURATION
# ============================================================

# Path to the JPlag JAR — lives next to main.py
JPLAG_JAR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jplag.jar")

# Minimum token match length. Lower = more sensitive but more false positives.
# JPlag default is 12. We use 5 for shorter student submissions.
DEFAULT_MIN_TOKEN_MATCH = 5

# Similarity threshold to flag a pair as suspicious
DEFAULT_SIMILARITY_THRESHOLD = 0.80  # 80%

# Subprocess timeout in seconds
JPLAG_TIMEOUT_SECONDS = 120


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class JPlagPairResult:
    """Similarity result for a single pair of submissions."""
    user_a: str
    user_b: str
    similarity: float          # 0.0 to 1.0
    similarity_pct: float      # 0.0 to 100.0
    flagged: bool              # True if above threshold
    matched_tokens: int = 0    # Number of matched tokens
    matched_files: List[Dict] = field(default_factory=list)


@dataclass
class JPlagReport:
    """Complete JPlag analysis report."""
    success: bool
    language: str
    total_submissions: int
    valid_submissions: int
    total_comparisons: int
    flagged_pairs: List[JPlagPairResult]
    all_pairs: List[JPlagPairResult]
    threshold_used: float
    execution_time_ms: int
    errors: List[str]
    jplag_version: str


# ============================================================
# CORE ENGINE
# ============================================================

def _check_prerequisites() -> Optional[str]:
    """Verify Java and JPlag JAR are available. Returns error message or None."""
    # Check Java
    java_path = shutil.which("java")
    if not java_path:
        return ("Java not found on system PATH. JPlag requires Java 17+. "
                "Install from https://adoptium.net/ and ensure 'java' is on PATH.")

    # Check JAR exists
    if not os.path.isfile(JPLAG_JAR_PATH):
        return (f"JPlag JAR not found at: {JPLAG_JAR_PATH}. "
                f"Download from https://github.com/jplag/JPlag/releases "
                f"and save as 'jplag.jar' in the backend directory.")

    return None


def _scaffold_directories(
    submissions: Dict[str, str],
    base_code: Optional[str] = None
) -> tuple:
    """
    Create the temporary directory structure JPlag requires.

    JPlag expects:
        root_dir/
            user1/
                user1.py
            user2/
                user2.py
            ...
        base_code_dir/    (optional — starter code given to all users)
            base.py

    Args:
        submissions: Dict mapping user_id -> Python source code
        base_code: Optional starter code that was given to all users
                   (JPlag ignores matches against base code)

    Returns:
        (temp_root, submissions_dir, base_code_dir_or_None)
    """
    temp_root = tempfile.mkdtemp(prefix="jplag_skillsync_")
    submissions_dir = os.path.join(temp_root, "submissions")
    os.makedirs(submissions_dir)

    # Create per-user submission folders
    for user_id, code in submissions.items():
        # Sanitize user_id for filesystem safety
        safe_name = re.sub(r'[^\w\-]', '_', user_id)
        user_dir = os.path.join(submissions_dir, safe_name)
        os.makedirs(user_dir, exist_ok=True)

        file_path = os.path.join(user_dir, f"{safe_name}.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

    # Create base code directory if provided
    base_code_dir = None
    if base_code and base_code.strip():
        base_code_dir = os.path.join(temp_root, "base_code")
        os.makedirs(base_code_dir)
        with open(os.path.join(base_code_dir, "base.py"), "w", encoding="utf-8") as f:
            f.write(base_code)

    return temp_root, submissions_dir, base_code_dir


def _build_command(
    submissions_dir: str,
    result_dir: str,
    base_code_dir: Optional[str] = None,
    min_token_match: int = DEFAULT_MIN_TOKEN_MATCH
) -> List[str]:
    """Build the JPlag CLI command."""
    cmd = [
        "java", "-jar", JPLAG_JAR_PATH,
        "-l", "python3",                    # Language: Python 3
        "-r", result_dir,                   # Output directory (JPlag appends .zip)
        "-t", str(min_token_match),         # Minimum token match length
        "-n", "200",                        # Max comparisons in report
    ]

    if base_code_dir:
        cmd.extend(["-bc", base_code_dir])  # Base code directory

    cmd.append(submissions_dir)             # Root directory with submissions

    return cmd


def _parse_results_zip(zip_path: str) -> Dict:
    """
    Parse the JPlag results ZIP file.

    The ZIP contains:
      - overview.json: Summary with pairwise similarity scores
      - userA-userB.json: Detailed match info per pair
      - files/: Copy of submission files

    Returns the parsed overview.json as a dict, or empty dict on failure.
    """
    if not os.path.isfile(zip_path):
        return {}

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            if "overview.json" in zf.namelist():
                content = zf.read("overview.json").decode("utf-8")
                return json.loads(content)
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as e:
        print(f"[JPLAG] Error parsing results ZIP: {e}")

    return {}


def _parse_stdout_scores(stdout: str) -> List[Dict]:
    """
    Fallback parser: extract pairwise scores from JPlag's stdout log lines.

    Example line:
      'Comparing user1-user2: 0.95'
    """
    pattern = re.compile(r"Comparing\s+(\S+)-(\S+):\s+([0-9.]+)")
    pairs = []
    for match in pattern.finditer(stdout):
        pairs.append({
            "user_a": match.group(1),
            "user_b": match.group(2),
            "similarity": float(match.group(3))
        })
    return pairs


def run_jplag(
    submissions: Dict[str, str],
    base_code: Optional[str] = None,
    min_token_match: int = DEFAULT_MIN_TOKEN_MATCH,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> JPlagReport:
    """
    Run JPlag on a set of Python code submissions.

    Args:
        submissions: Dict mapping user_id -> Python source code string.
                     Must have at least 2 submissions.
        base_code: Optional starter/template code given to all users.
                   JPlag will ignore token matches against this.
        min_token_match: Minimum consecutive matching tokens to count.
                         Lower = more sensitive. Default 5.
        similarity_threshold: Pairs above this are flagged. Default 0.80.

    Returns:
        JPlagReport with all pairwise similarity scores and flagged pairs.
    """
    errors = []

    # --- Prerequisites ---
    prereq_error = _check_prerequisites()
    if prereq_error:
        return JPlagReport(
            success=False, language="python3",
            total_submissions=len(submissions), valid_submissions=0,
            total_comparisons=0, flagged_pairs=[], all_pairs=[],
            threshold_used=similarity_threshold, execution_time_ms=0,
            errors=[prereq_error], jplag_version="unknown"
        )

    if len(submissions) < 2:
        return JPlagReport(
            success=False, language="python3",
            total_submissions=len(submissions), valid_submissions=0,
            total_comparisons=0, flagged_pairs=[], all_pairs=[],
            threshold_used=similarity_threshold, execution_time_ms=0,
            errors=["JPlag requires at least 2 submissions to compare."],
            jplag_version="unknown"
        )

    # --- Scaffold directories ---
    temp_root, submissions_dir, base_code_dir = _scaffold_directories(
        submissions, base_code
    )
    result_dir = os.path.join(temp_root, "results")

    try:
        # --- Build and run command ---
        cmd = _build_command(submissions_dir, result_dir, base_code_dir, min_token_match)
        print(f"[JPLAG] Running: {' '.join(cmd[:6])}... ({len(submissions)} submissions)")

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=JPLAG_TIMEOUT_SECONDS,
            encoding="utf-8",
            errors="replace"
        )

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        if proc.returncode != 0 and "Not enough valid submissions" in stdout:
            errors.append("JPlag: Not enough valid submissions (code may be too short).")
        elif proc.returncode != 0:
            errors.append(f"JPlag exited with code {proc.returncode}: {stderr[:500]}")

        # --- Parse results ---
        zip_path = result_dir + ".zip"
        overview = _parse_results_zip(zip_path)

        all_pairs = []
        jplag_version = "unknown"

        if overview:
            # Extract version
            ver = overview.get("jplag_version", {})
            jplag_version = f"{ver.get('major', '?')}.{ver.get('minor', '?')}.{ver.get('patch', '?')}"

            # Extract pairwise scores from metrics
            metrics = overview.get("metrics", [])
            id_to_name = overview.get("submission_id_to_display_name", {})

            if metrics:
                # Use AVG metric (first one) — this is JPlag's default
                avg_metric = metrics[0]
                for comp in avg_metric.get("topComparisons", []):
                    user_a_id = comp["first_submission"]
                    user_b_id = comp["second_submission"]
                    sim = comp["similarity"]

                    user_a = id_to_name.get(user_a_id, user_a_id)
                    user_b = id_to_name.get(user_b_id, user_b_id)

                    all_pairs.append(JPlagPairResult(
                        user_a=user_a,
                        user_b=user_b,
                        similarity=round(sim, 4),
                        similarity_pct=round(sim * 100, 1),
                        flagged=sim >= similarity_threshold
                    ))

            # Try to enrich with detailed match data from individual comparison files
            comp_files = overview.get("submission_ids_to_comparison_file_name", {})
            if os.path.isfile(zip_path):
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        for pair in all_pairs:
                            # Find the comparison JSON for this pair
                            comp_file = None
                            a_comps = comp_files.get(pair.user_a, {})
                            comp_file = a_comps.get(pair.user_b)
                            if not comp_file:
                                b_comps = comp_files.get(pair.user_b, {})
                                comp_file = b_comps.get(pair.user_a)

                            if comp_file and comp_file in zf.namelist():
                                detail = json.loads(zf.read(comp_file).decode("utf-8"))
                                matches = detail.get("matches", [])
                                total_tokens = sum(m.get("tokens", 0) for m in matches)
                                pair.matched_tokens = total_tokens
                                pair.matched_files = [
                                    {"file1": m.get("file1", ""),
                                     "file2": m.get("file2", ""),
                                     "tokens": m.get("tokens", 0)}
                                    for m in matches[:10]  # limit to 10 matches
                                ]
                except Exception as e:
                    errors.append(f"Error enriching match details: {e}")

        else:
            # Fallback: parse stdout for scores
            stdout_pairs = _parse_stdout_scores(stdout)
            for sp in stdout_pairs:
                sim = sp["similarity"]
                all_pairs.append(JPlagPairResult(
                    user_a=sp["user_a"],
                    user_b=sp["user_b"],
                    similarity=round(sim, 4),
                    similarity_pct=round(sim * 100, 1),
                    flagged=sim >= similarity_threshold
                ))

        # Collect failed submissions from overview
        failed = overview.get("failed_submission_names", [])
        if failed:
            errors.append(f"JPlag rejected submissions: {failed}")

        # Sort by similarity descending
        all_pairs.sort(key=lambda p: p.similarity, reverse=True)
        flagged_pairs = [p for p in all_pairs if p.flagged]

        valid_count = len(submissions) - len(failed)
        exec_time = overview.get("execution_time", 0)

        return JPlagReport(
            success=proc.returncode == 0 and len(all_pairs) > 0,
            language="python3",
            total_submissions=len(submissions),
            valid_submissions=valid_count,
            total_comparisons=overview.get("total_comparisons", len(all_pairs)),
            flagged_pairs=flagged_pairs,
            all_pairs=all_pairs,
            threshold_used=similarity_threshold,
            execution_time_ms=exec_time,
            errors=errors,
            jplag_version=jplag_version
        )

    except subprocess.TimeoutExpired:
        return JPlagReport(
            success=False, language="python3",
            total_submissions=len(submissions), valid_submissions=0,
            total_comparisons=0, flagged_pairs=[], all_pairs=[],
            threshold_used=similarity_threshold, execution_time_ms=0,
            errors=[f"JPlag timed out after {JPLAG_TIMEOUT_SECONDS}s"],
            jplag_version="unknown"
        )
    except Exception as e:
        return JPlagReport(
            success=False, language="python3",
            total_submissions=len(submissions), valid_submissions=0,
            total_comparisons=0, flagged_pairs=[], all_pairs=[],
            threshold_used=similarity_threshold, execution_time_ms=0,
            errors=[f"{type(e).__name__}: {e}"],
            jplag_version="unknown"
        )
    finally:
        # --- Cleanup ---
        shutil.rmtree(temp_root, ignore_errors=True)
        print(f"[JPLAG] Cleaned up temp directory: {temp_root}")


# ============================================================
# CONVENIENCE: Check if JPlag is available
# ============================================================

def is_jplag_available() -> Dict:
    """Check if JPlag can run on this system."""
    java_path = shutil.which("java")
    jar_exists = os.path.isfile(JPLAG_JAR_PATH)

    java_version = "unknown"
    if java_path:
        try:
            r = subprocess.run(
                ["java", "-version"], capture_output=True, text=True, timeout=10
            )
            version_line = (r.stderr or r.stdout).strip().split("\n")[0]
            java_version = version_line
        except Exception:
            pass

    return {
        "available": bool(java_path and jar_exists),
        "java_found": bool(java_path),
        "java_path": java_path or "not found",
        "java_version": java_version,
        "jplag_jar_found": jar_exists,
        "jplag_jar_path": JPLAG_JAR_PATH,
        "min_java_version": "17+"
    }


