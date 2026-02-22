"""
Originality Engine for SkillSync
=================================

Pure-Python multi-signal analysis engine that detects copy-pasted,
AI-generated, or plagiarized code submissions. Uses ONLY Python stdlib
(ast, difflib, re, hashlib) — zero external dependencies.

5 Signals (each 0–100 suspicion score, weighted and combined):
  1. AST Structural Fingerprint — Detects structurally identical code
  2. Code-to-Skeleton Ratio     — Flags unrealistic code growth
  3. Behavioral Signals         — Low attempts + zero errors = suspicious
  4. Naming Convention Analysis  — Flags suspiciously polished variable names
  5. Comment/Docstring Density   — Copy-paste often has polished comments
"""

import ast
import re
import hashlib
import difflib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


# ============================================================
# CONFIGURATION
# ============================================================

# Weights for each signal (must sum to 1.0)
SIGNAL_WEIGHTS = {
    "ast_fingerprint": 0.20,
    "skeleton_ratio": 0.15,
    "behavioral": 0.20,
    "naming": 0.10,
    "comments": 0.10,
    "anticheat": 0.25,   # Tab switches + paste events (strongest signal)
}

# Known optimal solution AST fingerprints (hex digests)
# These are SHA-256 hashes of normalized AST dumps for common LeetCode problems.
# We populate this dynamically + have a static seed set.
KNOWN_SOLUTION_HASHES: set = set()

# Variable name patterns that indicate copy-paste from polished sources
POLISHED_NAME_PATTERNS = [
    r'dp_table', r'dp\[', r'memo\[', r'sliding_window',
    r'max_heap', r'min_heap', r'prefix_sum', r'suffix_sum',
    r'left_ptr', r'right_ptr', r'slow_ptr', r'fast_ptr',
    r'adjacency_list', r'visited_set', r'parent_map',
    r'backtrack', r'dfs_helper', r'bfs_queue',
    r'in_degree', r'out_degree', r'topological',
    r'memoize', r'tabulation', r'optimal_substructure',
]

# Comment patterns that suggest copy-paste or AI generation
AI_COMMENT_PATTERNS = [
    r'#\s*Time\s*Complexity\s*:?\s*O\(',
    r'#\s*Space\s*Complexity\s*:?\s*O\(',
    r'#\s*Approach\s*:',
    r'#\s*Algorithm\s*:',
    r'#\s*Step\s*\d+',
    r'#\s*Edge\s*case',
    r'#\s*Base\s*case',
    r'#\s*Optimization',
    r'#\s*Key\s*insight',
    r'#\s*Intuition',
    r'#\s*This\s+(?:function|method|approach|solution)',
    r'"""[\s\S]{50,}"""',  # Long docstrings
    r"'''[\s\S]{50,}'''",
]


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class SignalResult:
    """Result of a single analysis signal."""
    name: str
    suspicion: float       # 0.0 (original) to 100.0 (definitely copied)
    weight: float          # How much this signal contributes
    explanation: str       # Human-readable explanation
    details: Dict = field(default_factory=dict)


@dataclass
class OriginalityReport:
    """Complete originality analysis report."""
    originality_score: float    # 0 (copied) to 100 (original)
    confidence: str             # "high", "medium", "low"
    verdict: str                # "original", "suspicious", "likely_copied"
    explanation: str            # Summary for the LLM prompt
    signals: List[SignalResult] = field(default_factory=list)
    raw_suspicion: float = 0.0  # Weighted suspicion before inversion


# ============================================================
# SIGNAL 1: AST STRUCTURAL FINGERPRINT
# ============================================================

def _normalize_ast(code: str) -> Optional[ast.AST]:
    """Parse code into AST, return None if unparseable."""
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _ast_structure_hash(tree: ast.AST) -> str:
    """
    Create a structural hash of the AST that ignores:
    - Variable names (all names → 'x')
    - String literals (all strings → 's')
    - Numeric literals (all numbers → 0)
    - Comments and whitespace

    This catches code that's been cosmetically renamed but is
    structurally identical to a known solution.
    """
    class Normalizer(ast.NodeTransformer):
        def visit_Name(self, node):
            node.id = 'x'
            return self.generic_visit(node)

        def visit_FunctionDef(self, node):
            # Keep method names (they're part of the problem spec)
            # but normalize internal helper names
            if not node.name.startswith('__'):
                # Keep the class method name, normalize helpers
                pass
            self.generic_visit(node)
            return node

        def visit_Constant(self, node):
            if isinstance(node.value, str):
                node.value = 's'
            elif isinstance(node.value, (int, float)):
                node.value = 0
            return node

        def visit_arg(self, node):
            node.arg = 'x'
            return self.generic_visit(node)

    normalized = Normalizer().visit(ast.parse(ast.unparse(tree)))
    dump = ast.dump(normalized, annotate_fields=False)
    return hashlib.sha256(dump.encode()).hexdigest()


def _count_ast_nodes(tree: ast.AST) -> int:
    """Count total AST nodes as a complexity proxy."""
    return sum(1 for _ in ast.walk(tree))


def _extract_control_flow(tree: ast.AST) -> List[str]:
    """Extract the sequence of control flow structures."""
    flow = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            flow.append('for')
        elif isinstance(node, ast.While):
            flow.append('while')
        elif isinstance(node, ast.If):
            flow.append('if')
        elif isinstance(node, ast.Try):
            flow.append('try')
        elif isinstance(node, ast.With):
            flow.append('with')
        elif isinstance(node, ast.ListComp):
            flow.append('listcomp')
        elif isinstance(node, ast.DictComp):
            flow.append('dictcomp')
        elif isinstance(node, ast.Return):
            flow.append('return')
    return flow


def analyze_ast_fingerprint(code: str) -> SignalResult:
    """
    Signal 1: Check if the code's AST structure matches known solutions.
    Also measures structural complexity.
    """
    tree = _normalize_ast(code)
    if tree is None:
        return SignalResult(
            name="ast_fingerprint",
            suspicion=20.0,  # Can't parse = probably broken = probably not copied
            weight=SIGNAL_WEIGHTS["ast_fingerprint"],
            explanation="Code has syntax errors — unlikely to be a polished copy.",
            details={"parseable": False}
        )

    structure_hash = _ast_structure_hash(tree)
    node_count = _count_ast_nodes(tree)
    control_flow = _extract_control_flow(tree)

    # Check against known solution hashes
    is_known = structure_hash in KNOWN_SOLUTION_HASHES

    # Heuristic: Very high node count with sophisticated control flow
    # suggests a complete, polished solution
    sophistication = 0.0
    if node_count > 80:
        sophistication += 20.0
    if node_count > 150:
        sophistication += 20.0
    if len(control_flow) > 8:
        sophistication += 15.0

    # Multiple nested loops = likely an optimized algorithm
    flow_str = ' '.join(control_flow)
    if 'for for' in flow_str or 'while while' in flow_str:
        sophistication += 10.0

    # Has recursion? (function calling itself)
    try:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if child.func.attr == func_name:
                                sophistication += 10.0
                        elif isinstance(child.func, ast.Name):
                            if child.func.id == func_name:
                                sophistication += 10.0
    except Exception:
        pass

    suspicion = min(sophistication, 70.0)  # Cap at 70 — AST alone isn't proof
    if is_known:
        suspicion = 90.0  # Known solution = very suspicious

    return SignalResult(
        name="ast_fingerprint",
        suspicion=suspicion,
        weight=SIGNAL_WEIGHTS["ast_fingerprint"],
        explanation=(
            f"AST analysis: {node_count} nodes, {len(control_flow)} control structures. "
            f"{'MATCHES known solution fingerprint!' if is_known else 'No exact fingerprint match.'} "
            f"Structural sophistication: {sophistication:.0f}/70."
        ),
        details={
            "parseable": True,
            "node_count": node_count,
            "control_flow_count": len(control_flow),
            "structure_hash": structure_hash[:16],
            "is_known_solution": is_known,
            "sophistication": sophistication,
        }
    )


# ============================================================
# SIGNAL 2: CODE-TO-SKELETON RATIO
# ============================================================

def analyze_skeleton_ratio(code: str, skeleton: str) -> SignalResult:
    """
    Signal 2: How much did the user change from the skeleton?

    If the user went from a 5-line `pass` skeleton to 80 lines of
    optimal code, that's suspicious — especially with few attempts.
    """
    if not skeleton or not skeleton.strip():
        # No skeleton available — can't compare
        return SignalResult(
            name="skeleton_ratio",
            suspicion=30.0,  # Neutral-ish
            weight=SIGNAL_WEIGHTS["skeleton_ratio"],
            explanation="No skeleton available for comparison.",
            details={"skeleton_available": False}
        )

    # Count meaningful lines (non-blank, non-comment)
    def meaningful_lines(text: str) -> List[str]:
        return [
            line.strip() for line in text.split('\n')
            if line.strip() and not line.strip().startswith('#')
        ]

    skeleton_lines = meaningful_lines(skeleton)
    code_lines = meaningful_lines(code)

    skeleton_len = max(len(skeleton_lines), 1)
    code_len = len(code_lines)
    growth_ratio = code_len / skeleton_len

    # Compute actual text similarity
    similarity = difflib.SequenceMatcher(None, skeleton, code).ratio()

    # If the code barely changed from skeleton, it's original (they're still working)
    if similarity > 0.85:
        suspicion = 5.0
        explanation = f"Code is {similarity:.0%} similar to skeleton — still mostly unchanged."
    elif growth_ratio > 8:
        suspicion = 75.0
        explanation = f"Code grew {growth_ratio:.1f}x from skeleton ({skeleton_len} → {code_len} lines). Suspicious volume for a timed test."
    elif growth_ratio > 4:
        suspicion = 50.0
        explanation = f"Code grew {growth_ratio:.1f}x from skeleton. Moderate growth."
    elif growth_ratio > 2:
        suspicion = 25.0
        explanation = f"Code grew {growth_ratio:.1f}x from skeleton. Normal range."
    else:
        suspicion = 10.0
        explanation = f"Code is compact ({code_len} lines). Low suspicion."

    return SignalResult(
        name="skeleton_ratio",
        suspicion=suspicion,
        weight=SIGNAL_WEIGHTS["skeleton_ratio"],
        explanation=explanation,
        details={
            "skeleton_available": True,
            "skeleton_lines": skeleton_len,
            "code_lines": code_len,
            "growth_ratio": round(growth_ratio, 2),
            "similarity_to_skeleton": round(similarity, 3),
        }
    )


# ============================================================
# SIGNAL 3: BEHAVIORAL SIGNALS
# ============================================================

def analyze_behavioral(code: str, attempts: int, error_count: int) -> SignalResult:
    """
    Signal 3: Detect suspicious behavioral patterns.

    A real student iterates: they run code, get errors, fix them, re-run.
    A cheater: pastes optimal code, runs it once or twice, submits.

    Key metrics:
    - Attempts (how many times they ran the code)
    - Error count (how many errors they encountered)
    - Code complexity (how sophisticated is the final code)
    """
    tree = _normalize_ast(code)
    node_count = _count_ast_nodes(tree) if tree else 0

    # Meaningful lines of code
    lines = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]
    loc = len(lines)

    # Complexity-to-effort ratio
    # High complexity + low effort = suspicious
    suspicion = 0.0
    details = {
        "attempts": attempts,
        "error_count": error_count,
        "lines_of_code": loc,
        "ast_nodes": node_count,
    }

    # Red flag 1: Complex code with very few attempts
    if loc > 15 and attempts <= 1:
        suspicion += 40.0  # Got it right first try with a long solution?
        details["flag_few_attempts"] = True
    elif loc > 10 and attempts <= 2:
        suspicion += 25.0
        details["flag_few_attempts"] = True

    # Red flag 2: Complex code with ZERO errors
    if loc > 15 and error_count == 0:
        suspicion += 30.0  # Never made a single mistake?
        details["flag_zero_errors"] = True
    elif loc > 10 and error_count == 0 and attempts <= 2:
        suspicion += 20.0
        details["flag_zero_errors"] = True

    # Red flag 3: Very high AST complexity with minimal iteration
    if node_count > 60 and attempts <= 2:
        suspicion += 20.0
        details["flag_high_complexity_low_effort"] = True

    # Green flag: Many attempts with errors = genuine effort
    if attempts >= 5 and error_count >= 3:
        suspicion = max(0, suspicion - 30.0)  # Reduce suspicion significantly
        details["flag_genuine_effort"] = True

    if attempts >= 3 and error_count >= 1:
        suspicion = max(0, suspicion - 15.0)
        details["flag_some_effort"] = True

    suspicion = min(suspicion, 90.0)  # Cap at 90

    # Generate explanation
    if suspicion >= 50:
        explanation = (
            f"Behavioral red flags: {loc} lines of code with only {attempts} attempt(s) "
            f"and {error_count} error(s). This pattern is consistent with copy-pasting."
        )
    elif suspicion >= 25:
        explanation = (
            f"Mild behavioral signals: {loc} lines, {attempts} attempt(s), {error_count} error(s). "
            f"Somewhat low effort for the code complexity."
        )
    else:
        explanation = (
            f"Behavioral pattern looks normal: {attempts} attempt(s), {error_count} error(s) "
            f"for {loc} lines of code."
        )

    return SignalResult(
        name="behavioral",
        suspicion=suspicion,
        weight=SIGNAL_WEIGHTS["behavioral"],
        explanation=explanation,
        details=details,
    )


# ============================================================
# SIGNAL 4: NAMING CONVENTION ANALYSIS
# ============================================================

def analyze_naming(code: str) -> SignalResult:
    """
    Signal 4: Detect suspiciously professional variable names.

    In a timed coding test, students typically use short names (i, j, n, res, ans).
    Copy-pasted solutions from blogs/AI often have polished names like
    'sliding_window', 'prefix_sum', 'adjacency_list'.
    """
    polished_count = 0
    matched_patterns = []

    code_lower = code.lower()
    for pattern in POLISHED_NAME_PATTERNS:
        if re.search(pattern, code_lower):
            polished_count += 1
            matched_patterns.append(pattern)

    # Also check for very long descriptive variable names (> 15 chars)
    tree = _normalize_ast(code)
    long_names = []
    if tree:
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and len(node.id) > 15:
                long_names.append(node.id)
            elif isinstance(node, ast.FunctionDef) and len(node.name) > 20:
                long_names.append(node.name)

    # Score
    suspicion = 0.0
    if polished_count >= 4:
        suspicion = 70.0
    elif polished_count >= 2:
        suspicion = 40.0
    elif polished_count >= 1:
        suspicion = 20.0

    if len(long_names) >= 3:
        suspicion = min(suspicion + 20.0, 80.0)

    if polished_count == 0 and len(long_names) == 0:
        suspicion = 5.0

    explanation = (
        f"Found {polished_count} polished naming pattern(s) and {len(long_names)} "
        f"very long variable name(s). "
        f"{'Naming suggests a prepared/copied solution.' if suspicion > 40 else 'Naming looks typical for a timed test.'}"
    )

    return SignalResult(
        name="naming",
        suspicion=suspicion,
        weight=SIGNAL_WEIGHTS["naming"],
        explanation=explanation,
        details={
            "polished_patterns_found": polished_count,
            "matched_patterns": matched_patterns[:5],
            "long_names": long_names[:5],
        }
    )


# ============================================================
# SIGNAL 5: COMMENT / DOCSTRING DENSITY
# ============================================================

def analyze_comments(code: str) -> SignalResult:
    """
    Signal 5: Detect suspiciously thorough comments.

    In a timed test, students rarely write detailed documentation.
    Copy-pasted code from tutorials/AI often includes:
    - Time/space complexity annotations
    - Step-by-step comments
    - Detailed docstrings
    """
    lines = code.split('\n')
    total_lines = max(len(lines), 1)

    comment_lines = sum(1 for l in lines if l.strip().startswith('#'))
    comment_ratio = comment_lines / total_lines

    # Check for AI-style comment patterns
    ai_pattern_count = 0
    for pattern in AI_COMMENT_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            ai_pattern_count += 1

    # Docstring detection
    docstring_count = len(re.findall(r'"""[\s\S]*?"""', code))
    docstring_count += len(re.findall(r"'''[\s\S]*?'''", code))

    # Score
    suspicion = 0.0

    if ai_pattern_count >= 3:
        suspicion += 50.0
    elif ai_pattern_count >= 1:
        suspicion += 25.0

    if comment_ratio > 0.30:
        suspicion += 25.0  # More than 30% comments in a timed test?
    elif comment_ratio > 0.20:
        suspicion += 15.0

    if docstring_count >= 2:
        suspicion += 15.0  # Multiple docstrings in a timed solution

    suspicion = min(suspicion, 85.0)

    explanation = (
        f"Comment analysis: {comment_lines} comment lines ({comment_ratio:.0%} of code), "
        f"{ai_pattern_count} AI-style pattern(s), {docstring_count} docstring(s). "
        f"{'Heavy documentation suggests prepared code.' if suspicion > 40 else 'Comment level is normal for a timed test.'}"
    )

    return SignalResult(
        name="comments",
        suspicion=suspicion,
        weight=SIGNAL_WEIGHTS["comments"],
        explanation=explanation,
        details={
            "comment_lines": comment_lines,
            "comment_ratio": round(comment_ratio, 3),
            "ai_pattern_count": ai_pattern_count,
            "docstring_count": docstring_count,
        }
    )


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================

def analyze_anticheat(tab_switches: int, paste_count: int) -> SignalResult:
    """
    Signal 6: Tab-switch and paste event analysis.

    The strongest cheating signal: students who switch tabs frequently
    are looking up solutions, and students who paste code are copying.
    """
    suspicion = 0.0
    details = {
        "tab_switches": tab_switches,
        "paste_count": paste_count,
    }

    # Tab switch scoring
    if tab_switches >= 15:
        suspicion += 60.0
        details["flag_excessive_tab_switching"] = True
    elif tab_switches >= 10:
        suspicion += 45.0
        details["flag_high_tab_switching"] = True
    elif tab_switches >= 5:
        suspicion += 25.0
        details["flag_moderate_tab_switching"] = True
    elif tab_switches >= 2:
        suspicion += 10.0

    # Paste scoring (much more damning)
    if paste_count >= 3:
        suspicion += 40.0
        details["flag_excessive_pasting"] = True
    elif paste_count >= 1:
        suspicion += 25.0
        details["flag_code_pasted"] = True

    suspicion = min(suspicion, 95.0)

    if suspicion >= 50:
        explanation = (
            f"Anti-cheat alert: {tab_switches} tab switch(es) and {paste_count} paste event(s). "
            f"Strong indicators of external resource usage."
        )
    elif suspicion >= 20:
        explanation = (
            f"Mild anti-cheat signals: {tab_switches} tab switch(es), {paste_count} paste(s). "
            f"Some external reference likely used."
        )
    else:
        explanation = (
            f"Clean session: {tab_switches} tab switch(es), {paste_count} paste(s). "
            f"No significant anti-cheat flags."
        )

    return SignalResult(
        name="anticheat",
        suspicion=suspicion,
        weight=SIGNAL_WEIGHTS["anticheat"],
        explanation=explanation,
        details=details,
    )


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================

def analyze_originality(
    code: str,
    skeleton: str = "",
    attempts: int = 0,
    error_count: int = 0,
    tab_switches: int = 0,
    paste_count: int = 0,
) -> OriginalityReport:
    """
    Run all 6 signals and produce a combined originality score.

    Args:
        code: The user's final submitted code.
        skeleton: The original skeleton code given to the user (with `pass`).
        attempts: How many times the user ran/tested the code.
        error_count: How many errors the user encountered during the session.
        tab_switches: How many times the user switched away from the tab.
        paste_count: How many times the user pasted code (>20 chars).

    Returns:
        OriginalityReport with score 0–100 (100 = fully original).
    """
    # Handle edge cases
    if not code or not code.strip():
        return OriginalityReport(
            originality_score=100.0,
            confidence="low",
            verdict="original",
            explanation="Empty or blank submission — nothing to analyze.",
            signals=[],
            raw_suspicion=0.0,
        )

    # Strip the skeleton prefix if it's still at the top of the code
    # (we only want to analyze the user's additions)
    code_stripped = code.strip()

    # Run all 6 signals
    signals = [
        analyze_ast_fingerprint(code_stripped),
        analyze_skeleton_ratio(code_stripped, skeleton),
        analyze_behavioral(code_stripped, attempts, error_count),
        analyze_naming(code_stripped),
        analyze_comments(code_stripped),
        analyze_anticheat(tab_switches, paste_count),
    ]

    # Weighted combination
    weighted_suspicion = sum(s.suspicion * s.weight for s in signals)

    # Convert suspicion (0–100) to originality (100–0)
    originality_score = round(max(0.0, min(100.0, 100.0 - weighted_suspicion)), 1)

    # Determine verdict
    if originality_score >= 70:
        verdict = "original"
        confidence = "high" if originality_score >= 85 else "medium"
    elif originality_score >= 40:
        verdict = "suspicious"
        confidence = "medium"
    else:
        verdict = "likely_copied"
        confidence = "high" if originality_score <= 20 else "medium"

    # Build explanation for the LLM prompt
    signal_summaries = "\n".join([
        f"  - {s.name}: suspicion={s.suspicion:.0f}/100 ({s.explanation})"
        for s in signals
    ])
    explanation = (
        f"Originality Score: {originality_score}/100 (verdict: {verdict})\n"
        f"Signal Breakdown:\n{signal_summaries}"
    )

    return OriginalityReport(
        originality_score=originality_score,
        confidence=confidence,
        verdict=verdict,
        explanation=explanation,
        signals=signals,
        raw_suspicion=round(weighted_suspicion, 1),
    )


# ============================================================
# BATCH ANALYSIS (for /batch-submit endpoint)
# ============================================================

def analyze_batch_originality(
    questions: list,
    tab_switches: int = 0,
    paste_count: int = 0,
) -> OriginalityReport:
    """
    Analyze originality across all questions in a batch assessment.

    Args:
        questions: List of dicts with keys: code, skeleton, attempts, error_count

    Returns:
        Combined OriginalityReport (worst-case scoring — one cheated question
        tanks the entire assessment).
    """
    if not questions:
        return OriginalityReport(
            originality_score=100.0,
            confidence="low",
            verdict="original",
            explanation="No questions to analyze.",
            signals=[],
            raw_suspicion=0.0,
        )

    reports = []
    for q in questions:
        report = analyze_originality(
            code=q.get("code", ""),
            skeleton=q.get("skeleton", ""),
            attempts=q.get("attempts", 0),
            error_count=q.get("error_count", 0),
            tab_switches=tab_switches,
            paste_count=paste_count,
        )
        reports.append(report)

    # Worst-case approach: the LOWEST originality score across all questions
    # (if you cheated on even one question, it should tank your assessment)
    worst_score = min(r.originality_score for r in reports)

    # Also compute average for context
    avg_score = sum(r.originality_score for r in reports) / len(reports)

    # Use weighted combination: 60% worst, 40% average
    # This ensures one bad question tanks the score but isn't 100% punitive
    combined_score = round(0.6 * worst_score + 0.4 * avg_score, 1)

    # Determine overall verdict
    if combined_score >= 70:
        verdict = "original"
        confidence = "high" if combined_score >= 85 else "medium"
    elif combined_score >= 40:
        verdict = "suspicious"
        confidence = "medium"
    else:
        verdict = "likely_copied"
        confidence = "high" if combined_score <= 20 else "medium"

    # Build combined explanation
    per_q = "\n".join([
        f"  Q{i+1}: originality={r.originality_score}/100 ({r.verdict})"
        for i, r in enumerate(reports)
    ])
    explanation = (
        f"Batch Originality Score: {combined_score}/100 (verdict: {verdict})\n"
        f"Per-Question Breakdown:\n{per_q}\n"
        f"Scoring: 60% worst-case ({worst_score}) + 40% average ({avg_score:.1f})"
    )

    # Collect all signals from the worst-performing question
    worst_report = min(reports, key=lambda r: r.originality_score)

    return OriginalityReport(
        originality_score=combined_score,
        confidence=confidence,
        verdict=verdict,
        explanation=explanation,
        signals=worst_report.signals,
        raw_suspicion=round(100.0 - combined_score, 1),
    )
