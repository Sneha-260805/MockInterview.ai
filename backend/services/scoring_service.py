"""
Pure, stateless scoring functions. No external dependencies — works without LLM.
All inputs are plain strings/lists; all outputs are ints or strings.
"""

import re

# ── Text normalisation ────────────────────────────────────────────────────────

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "for", "with",
    "how", "what", "when", "where", "which", "that", "this", "are",
    "is", "be", "by", "on", "at", "as", "from", "it", "its", "use",
}


def _normalise(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower())


def _key_terms(phrase: str) -> list[str]:
    words = _normalise(phrase).split()
    return [w for w in words if w not in _STOPWORDS and len(w) >= 3]


# ── Keyword coverage ──────────────────────────────────────────────────────────

def _point_covered(answer_lower: str, point: str) -> bool:
    terms = _key_terms(point)
    if not terms:
        return False
    for term in terms:
        if term in answer_lower:
            return True
        # Prefix match catches plurals/conjugations for terms ≥ 6 chars
        # e.g. "authentication" → prefix "authen" matches "authenticate"
        if len(term) >= 6 and term[:6] in answer_lower:
            return True
    return False


def keyword_coverage(
    answer: str, expected_points: list[str]
) -> tuple[float, list[str], list[str]]:
    """
    Returns (coverage_ratio 0–1, covered_points, missing_points).
    covered/missing lists use the original expected_point strings.
    """
    if not expected_points:
        return 1.0, [], []

    answer_lower = _normalise(answer)
    covered, missing = [], []

    for pt in expected_points:
        (covered if _point_covered(answer_lower, pt) else missing).append(pt)

    ratio = len(covered) / len(expected_points)
    return ratio, covered, missing


# ── Individual dimension scores ───────────────────────────────────────────────

def depth_score(answer: str) -> int:
    """Estimate answer depth from length and structural signals (0–95)."""
    words = answer.split()
    wc = len(words)

    if wc < 20:
        base = 15
    elif wc < 50:
        base = 30
    elif wc < 100:
        base = 50
    elif wc < 200:
        base = 65
    else:
        base = 75

    al = answer.lower()
    signals = sum([
        bool(re.search(r"\b(first|second|third|finally|additionally|furthermore|also)\b", al)),
        bool(re.search(r"\b(for example|such as|specifically|in particular|like)\b", al)),
        bool(re.search(r"\b(because|therefore|since|as a result|which means)\b", al)),
        bool(re.search(r"\b(trade.?off|however|although|on the other hand|but)\b", al)),
        bool(re.search(r"\d+", answer)),               # numbers / metrics
        bool(re.search(r"\b(i built|i implemented|i used|i chose|we decided)\b", al)),  # personal experience
    ])

    return min(base + signals * 3, 95)


def correctness_score(coverage_ratio: float) -> int:
    """Estimate technical correctness from keyword coverage (0–95)."""
    if coverage_ratio >= 0.8:
        return 82
    if coverage_ratio >= 0.6:
        return 68
    if coverage_ratio >= 0.4:
        return 52
    if coverage_ratio >= 0.2:
        return 36
    return 20


def technical_score_rule_based(coverage_ratio: float, depth: int) -> int:
    """Combine coverage and depth into a technical score (0–100)."""
    return min(int(coverage_ratio * 100 * 0.7 + depth * 0.3), 100)


def technical_score_with_llm(semantic: int, coverage_ratio: float) -> int:
    """Blend LLM semantic score with keyword coverage (0–100)."""
    return min(int(semantic * 0.7 + coverage_ratio * 100 * 0.3), 100)


# ── Feedback generation ───────────────────────────────────────────────────────

def generate_feedback(
    covered: list[str],
    missing: list[str],
    tech: int,
    depth: int,
) -> str:
    n_miss = len(missing)

    if tech >= 75:
        opening = "Strong answer that demonstrates solid technical understanding."
    elif tech >= 58:
        opening = "Good foundational answer with room to go a bit deeper."
    elif tech >= 40:
        opening = "The answer shows basic awareness of the topic but lacks important specifics."
    else:
        opening = "The response is directionally correct but needs significantly more depth and detail."

    if n_miss == 0:
        middle = "All expected points were covered — excellent thoroughness."
    elif n_miss == 1:
        middle = f"One area to strengthen: '{missing[0]}'."
    elif n_miss == 2:
        middle = f"Consider expanding on '{missing[0]}' and '{missing[1]}'."
    else:
        top2 = f"'{missing[0]}' and '{missing[1]}'"
        middle = f"Key gaps include {top2}, plus {n_miss - 2} other point(s)."

    if depth < 35:
        closing = "Try to include concrete examples and explain the reasoning behind your choices."
    elif depth < 60:
        closing = "Adding specific examples or discussing trade-offs would strengthen the answer further."
    else:
        closing = "Good level of detail — keep drawing on your real project experience."

    return f"{opening} {middle} {closing}"
