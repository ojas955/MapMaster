"""
Plagiarism Detection Engine for SkillSync
==========================================

Two independent detection strategies:

1. CODE PLAGIARISM (AST Structural Fingerprinting)
   - Parses Python source into an AST
   - Strips all variable names, comments, whitespace, and string literals
   - Produces a canonical "structural token sequence"
   - Compares sequences with TF-IDF cosine similarity
   - Catches: variable renaming, comment changes, whitespace tricks,
     reordering of independent statements

2. TEXT PLAGIARISM (TF-IDF Cosine Similarity)
   - Converts free-text answers into TF-IDF vectors
   - Measures cosine similarity between the new submission and every
     stored historical submission
   - Lightweight, no GPU, no external API keys

Both strategies are 100% open-source and run locally.
"""

import ast
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# 1. AST-BASED CODE PLAGIARISM DETECTOR
# ============================================================

class ASTNormalizer(ast.NodeVisitor):
    """
    Walks a Python AST and emits a sequence of structural tokens.

    Normalization rules (makes detection rename-proof):
    - All variable/function/class names -> generic placeholders (VAR, FUNC, CLS)
    - All string/number/boolean literals -> generic tokens (STR, NUM, BOOL)
    - All comments and docstrings are stripped (AST ignores them anyway)
    - Structural nodes are kept: If, For, While, FunctionDef, Return, etc.

    The resulting token sequence captures the STRUCTURE of the code,
    not its surface-level text. Two programs that do the same thing
    with different variable names will produce identical token sequences.
    """

    def __init__(self):
        self.tokens: List[str] = []

    def _emit(self, token: str):
        self.tokens.append(token)

    # --- Structural Nodes (the skeleton of the code) ---

    def visit_FunctionDef(self, node):
        self._emit("FUNC_DEF")
        # Emit parameter count (structural signal, not names)
        self._emit(f"PARAMS_{len(node.args.args)}")
        self.generic_visit(node)
        self._emit("END_FUNC")

    def visit_AsyncFunctionDef(self, node):
        self._emit("ASYNC_FUNC_DEF")
        self._emit(f"PARAMS_{len(node.args.args)}")
        self.generic_visit(node)
        self._emit("END_FUNC")

    def visit_ClassDef(self, node):
        self._emit("CLASS_DEF")
        self._emit(f"BASES_{len(node.bases)}")
        self.generic_visit(node)
        self._emit("END_CLASS")

    def visit_Return(self, node):
        self._emit("RETURN")
        self.generic_visit(node)

    def visit_Assign(self, node):
        self._emit("ASSIGN")
        self._emit(f"TARGETS_{len(node.targets)}")
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        op_name = type(node.op).__name__
        self._emit(f"AUG_ASSIGN_{op_name}")
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self._emit("ANN_ASSIGN")
        self.generic_visit(node)

    # --- Control Flow ---

    def visit_If(self, node):
        self._emit("IF")
        self.generic_visit(node)
        if node.orelse:
            self._emit("ELSE")
        self._emit("END_IF")

    def visit_For(self, node):
        self._emit("FOR")
        self.generic_visit(node)
        self._emit("END_FOR")

    def visit_While(self, node):
        self._emit("WHILE")
        self.generic_visit(node)
        self._emit("END_WHILE")

    def visit_Try(self, node):
        self._emit("TRY")
        self.generic_visit(node)
        self._emit("END_TRY")

    def visit_ExceptHandler(self, node):
        self._emit("EXCEPT")
        self.generic_visit(node)

    def visit_With(self, node):
        self._emit("WITH")
        self.generic_visit(node)

    def visit_Break(self, node):
        self._emit("BREAK")

    def visit_Continue(self, node):
        self._emit("CONTINUE")

    def visit_Pass(self, node):
        self._emit("PASS")

    # --- Expressions ---

    def visit_Call(self, node):
        self._emit("CALL")
        self._emit(f"ARGS_{len(node.args)}")
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        op_name = type(node.op).__name__
        self._emit(f"BOOL_{op_name}")
        self.generic_visit(node)

    def visit_BinOp(self, node):
        op_name = type(node.op).__name__
        self._emit(f"BIN_{op_name}")
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        op_name = type(node.op).__name__
        self._emit(f"UNARY_{op_name}")
        self.generic_visit(node)

    def visit_Compare(self, node):
        ops = "_".join(type(op).__name__ for op in node.ops)
        self._emit(f"CMP_{ops}")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        self._emit("SUBSCRIPT")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        self._emit("ATTR")
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self._emit("LIST_COMP")
        self.generic_visit(node)

    def visit_DictComp(self, node):
        self._emit("DICT_COMP")
        self.generic_visit(node)

    def visit_SetComp(self, node):
        self._emit("SET_COMP")
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):
        self._emit("GEN_EXPR")
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self._emit("LAMBDA")
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self._emit("TERNARY")
        self.generic_visit(node)

    # --- Literals (normalized to type tokens, not values) ---

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            self._emit("BOOL")
        elif isinstance(node.value, int):
            self._emit("NUM")
        elif isinstance(node.value, float):
            self._emit("FLOAT")
        elif isinstance(node.value, str):
            # Skip docstrings (strings that are expression statements)
            self._emit("STR")
        elif node.value is None:
            self._emit("NONE")

    def visit_List(self, node):
        self._emit(f"LIST_{len(node.elts)}")
        self.generic_visit(node)

    def visit_Tuple(self, node):
        self._emit(f"TUPLE_{len(node.elts)}")
        self.generic_visit(node)

    def visit_Dict(self, node):
        self._emit(f"DICT_{len(node.keys)}")
        self.generic_visit(node)

    def visit_Set(self, node):
        self._emit(f"SET_{len(node.elts)}")
        self.generic_visit(node)

    # --- Names (all normalized — this is what defeats variable renaming) ---

    def visit_Name(self, node):
        # Preserve built-in names that are structurally significant
        builtins = {'True', 'False', 'None', 'print', 'len', 'range',
                    'int', 'str', 'float', 'list', 'dict', 'set', 'tuple',
                    'sorted', 'reversed', 'enumerate', 'zip', 'map', 'filter',
                    'max', 'min', 'sum', 'abs', 'any', 'all', 'isinstance',
                    'type', 'super', 'self', 'cls'}
        if node.id in builtins:
            self._emit(f"BUILTIN_{node.id}")
        else:
            self._emit("VAR")

    # --- Import structure ---

    def visit_Import(self, node):
        self._emit(f"IMPORT_{len(node.names)}")

    def visit_ImportFrom(self, node):
        self._emit(f"FROM_IMPORT_{len(node.names)}")


def code_to_structural_tokens(source_code: str) -> str:
    """
    Parse Python source code and return a normalized structural token string.

    Returns empty string if the code can't be parsed (syntax errors).
    This is the "fingerprint" that's compared between submissions.
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        # If the code has syntax errors, fall back to a simple text-based
        # normalization: strip comments, normalize whitespace
        lines = source_code.strip().split('\n')
        normalized_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                # Remove inline comments
                if '#' in stripped:
                    stripped = stripped[:stripped.index('#')].rstrip()
                if stripped:
                    normalized_lines.append(stripped)
        return ' '.join(normalized_lines)

    normalizer = ASTNormalizer()
    normalizer.visit(tree)
    return ' '.join(normalizer.tokens)


# ============================================================
# 2. TF-IDF TEXT PLAGIARISM DETECTOR
# ============================================================

def compute_text_similarity(new_text: str, corpus: List[str]) -> List[float]:
    """
    Compare a new text submission against a corpus of previous submissions
    using TF-IDF vectorization + cosine similarity.

    Returns a list of similarity scores (0.0 to 1.0) — one per corpus entry.
    """
    if not corpus:
        return []

    # Combine new text with corpus for consistent TF-IDF vocabulary
    all_texts = [new_text] + corpus

    vectorizer = TfidfVectorizer(
        stop_words='english',
        ngram_range=(1, 3),    # unigrams + bigrams + trigrams for phrase matching
        max_features=10000,
        sublinear_tf=True       # apply log normalization to term frequencies
    )

    tfidf_matrix = vectorizer.fit_transform(all_texts)

    # Compare new_text (row 0) against all corpus entries (rows 1+)
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])

    return similarities[0].tolist()


def compute_code_similarity(new_code: str, corpus: List[str]) -> List[float]:
    """
    Compare a new code submission against a corpus of previous code submissions.

    Pipeline:
    1. Convert each code sample to structural AST tokens
    2. Use TF-IDF on the token sequences (treating tokens like "words")
    3. Compute cosine similarity

    This catches: variable renaming, comment changes, whitespace changes,
    string literal changes, and simple statement reordering.
    """
    if not corpus:
        return []

    # Convert all code to structural tokens
    new_tokens = code_to_structural_tokens(new_code)
    corpus_tokens = [code_to_structural_tokens(code) for code in corpus]

    # Skip if new code produced no tokens (empty/trivial submission)
    if not new_tokens.strip():
        return [0.0] * len(corpus)

    # Filter out empty corpus entries (unparseable code)
    all_token_strings = [new_tokens] + corpus_tokens

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 4),    # capture structural patterns up to 4 tokens long
        max_features=5000,
        analyzer='word'         # tokens are space-separated
    )

    tfidf_matrix = vectorizer.fit_transform(all_token_strings)

    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])

    return similarities[0].tolist()


# ============================================================
# 3. IN-MEMORY SUBMISSION STORE
# ============================================================
# In production, replace with a real database (PostgreSQL, MongoDB, etc.)

@dataclass
class StoredSubmission:
    """A historical submission stored for plagiarism comparison."""
    submission_id: str
    user_id: str
    question_id: str
    code: str
    code_tokens: str              # pre-computed AST token fingerprint
    text_answer: str
    submitted_at: str
    similarity_checked: bool = False


class SubmissionStore:
    """
    In-memory store for historical submissions.

    In production, this would be backed by a database.
    The store is keyed by question_id so we only compare submissions
    for the same question (apples to apples).
    """

    def __init__(self):
        # question_id -> list of stored submissions
        self._store: Dict[str, List[StoredSubmission]] = {}
        self._counter = 0

    def add_submission(
        self,
        user_id: str,
        question_id: str,
        code: str,
        text_answer: str = ""
    ) -> StoredSubmission:
        """Store a new submission and return the stored record."""
        self._counter += 1
        submission = StoredSubmission(
            submission_id=f"SUB-{self._counter:06d}",
            user_id=user_id,
            question_id=question_id,
            code=code,
            code_tokens=code_to_structural_tokens(code),
            text_answer=text_answer,
            submitted_at=datetime.now(timezone.utc).isoformat()
        )

        if question_id not in self._store:
            self._store[question_id] = []
        self._store[question_id].append(submission)

        return submission

    def get_submissions_for_question(
        self,
        question_id: str,
        exclude_user_id: Optional[str] = None
    ) -> List[StoredSubmission]:
        """Get all stored submissions for a question, optionally excluding a user."""
        submissions = self._store.get(question_id, [])
        if exclude_user_id:
            return [s for s in submissions if s.user_id != exclude_user_id]
        return submissions

    def get_stats(self) -> Dict:
        """Get store statistics."""
        total = sum(len(subs) for subs in self._store.values())
        return {
            "total_submissions": total,
            "unique_questions": len(self._store),
            "questions": {qid: len(subs) for qid, subs in self._store.items()}
        }

    def clear(self):
        """Clear all stored submissions."""
        self._store.clear()
        self._counter = 0


# ============================================================
# 4. PLAGIARISM CHECK ORCHESTRATOR
# ============================================================

@dataclass
class PlagiarismMatch:
    """A single plagiarism match against a historical submission."""
    matched_submission_id: str
    matched_user_id: str
    code_similarity: float        # 0.0 - 1.0
    text_similarity: float        # 0.0 - 1.0
    combined_score: float         # weighted average
    flag_level: str               # "clear" | "suspicious" | "flagged"


@dataclass
class PlagiarismReport:
    """Complete plagiarism report for a submission."""
    submission_id: str
    question_id: str
    user_id: str
    max_code_similarity: float
    max_text_similarity: float
    overall_risk_score: float
    risk_level: str               # "clear" | "low" | "medium" | "high"
    comparisons_made: int
    matches: List[PlagiarismMatch]
    details: str


# Thresholds (tunable)
CODE_SUSPICIOUS_THRESHOLD = 0.70   # 70% structural similarity
CODE_FLAGGED_THRESHOLD = 0.85      # 85% structural similarity
TEXT_SUSPICIOUS_THRESHOLD = 0.60   # 60% text similarity
TEXT_FLAGGED_THRESHOLD = 0.80      # 80% text similarity


def check_plagiarism(
    user_id: str,
    question_id: str,
    code: str,
    text_answer: str,
    store: SubmissionStore
) -> PlagiarismReport:
    """
    Run full plagiarism check on a new submission.

    1. Fetch all previous submissions for the same question (excluding this user)
    2. Compare code via AST structural similarity
    3. Compare text via TF-IDF cosine similarity
    4. Generate a combined risk report
    """

    # Get historical submissions for the same question
    historical = store.get_submissions_for_question(question_id, exclude_user_id=user_id)

    if not historical:
        # No historical data to compare against — first submission
        stored = store.add_submission(user_id, question_id, code, text_answer)
        return PlagiarismReport(
            submission_id=stored.submission_id,
            question_id=question_id,
            user_id=user_id,
            max_code_similarity=0.0,
            max_text_similarity=0.0,
            overall_risk_score=0.0,
            risk_level="clear",
            comparisons_made=0,
            matches=[],
            details="First submission for this question. No comparisons available."
        )

    # Run code similarity check
    historical_code = [s.code for s in historical]
    code_scores = compute_code_similarity(code, historical_code)

    # Run text similarity check (only if text is provided)
    text_scores = []
    if text_answer.strip():
        historical_texts = [s.text_answer for s in historical if s.text_answer.strip()]
        if historical_texts:
            text_scores = compute_text_similarity(text_answer, historical_texts)

    # Build match reports
    matches = []
    for i, sub in enumerate(historical):
        c_score = code_scores[i] if i < len(code_scores) else 0.0
        t_score = text_scores[i] if i < len(text_scores) else 0.0

        # Weighted combination: code is weighted higher (70/30)
        combined = (0.7 * c_score + 0.3 * t_score) if text_answer.strip() else c_score

        # Determine flag level
        if c_score >= CODE_FLAGGED_THRESHOLD or t_score >= TEXT_FLAGGED_THRESHOLD:
            flag = "flagged"
        elif c_score >= CODE_SUSPICIOUS_THRESHOLD or t_score >= TEXT_SUSPICIOUS_THRESHOLD:
            flag = "suspicious"
        else:
            flag = "clear"

        matches.append(PlagiarismMatch(
            matched_submission_id=sub.submission_id,
            matched_user_id=sub.user_id,
            code_similarity=round(c_score, 4),
            text_similarity=round(t_score, 4),
            combined_score=round(combined, 4),
            flag_level=flag
        ))

    # Sort by combined score descending
    matches.sort(key=lambda m: m.combined_score, reverse=True)

    # Compute overall risk
    max_code = max((m.code_similarity for m in matches), default=0.0)
    max_text = max((m.text_similarity for m in matches), default=0.0)
    overall_risk = max(m.combined_score for m in matches) if matches else 0.0

    if overall_risk >= 0.85:
        risk_level = "high"
    elif overall_risk >= 0.70:
        risk_level = "medium"
    elif overall_risk >= 0.50:
        risk_level = "low"
    else:
        risk_level = "clear"

    flagged_count = sum(1 for m in matches if m.flag_level == "flagged")
    suspicious_count = sum(1 for m in matches if m.flag_level == "suspicious")

    details_parts = [
        f"Compared against {len(historical)} previous submission(s).",
        f"Highest code similarity: {max_code:.1%}",
        f"Highest text similarity: {max_text:.1%}" if text_answer.strip() else "No text answer provided.",
    ]
    if flagged_count:
        details_parts.append(f"FLAGGED: {flagged_count} submission(s) exceed plagiarism threshold.")
    if suspicious_count:
        details_parts.append(f"SUSPICIOUS: {suspicious_count} submission(s) show moderate similarity.")
    if risk_level == "clear":
        details_parts.append("No significant similarity detected.")

    # Store the new submission for future comparisons
    stored = store.add_submission(user_id, question_id, code, text_answer)

    return PlagiarismReport(
        submission_id=stored.submission_id,
        question_id=question_id,
        user_id=user_id,
        max_code_similarity=round(max_code, 4),
        max_text_similarity=round(max_text, 4),
        overall_risk_score=round(overall_risk, 4),
        risk_level=risk_level,
        comparisons_made=len(historical),
        matches=matches[:5],  # Return top 5 matches only
        details=" ".join(details_parts)
    )



