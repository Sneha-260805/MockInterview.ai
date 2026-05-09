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
    """
    Estimate technical correctness from semantic concept coverage (0–95).

    Uses a smooth linear mapping instead of a step function to avoid harsh cliffs:
      0%  coverage → 25   (attempted answer, some credit)
      25% coverage → 42
      50% coverage → 59
      75% coverage → 75
      100% coverage → 92

    The old step function had 14-pt cliffs (e.g. 0.6→68, 0.4→52).
    This version rewards every additional concept covered proportionally.
    """
    score = 25 + round(coverage_ratio * 67)
    return max(20, min(95, score))


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
    """
    Interviewer-style feedback: constructive, encouraging, competence-oriented.
    Tone target: supportive senior engineer, not academic grader.
    """
    n_miss = len(missing)

    # ── Opening: performance signal ───────────────────────────────────────────
    if tech >= 78:
        opening = "Great answer — you clearly have a strong grasp of this area and covered the key points well."
    elif tech >= 65:
        opening = "Good answer. You've got the right foundations and showed solid understanding of the core concepts."
    elif tech >= 50:
        opening = "You're on the right track. There's enough here to show real familiarity — the next step is adding more specifics."
    elif tech >= 35:
        opening = "The core idea is there. In a real interview, push yourself to go one layer deeper with concrete details or trade-offs."
    else:
        opening = "You touched on the general area, but the answer needs more depth. Try explaining the 'why' and walking through a concrete example."

    # ── Middle: coverage gaps (encouraging, not list-heavy) ───────────────────
    if n_miss == 0:
        middle = "You covered everything expected — that's exactly the level of thoroughness interviewers look for."
    elif n_miss == 1:
        middle = f"One thing worth adding next time: {missing[0]}."
    elif n_miss == 2:
        middle = f"To round it out, try weaving in {missing[0]} and {missing[1]}."
    else:
        top2 = f"{missing[0]} and {missing[1]}"
        middle = (
            f"The two highest-impact additions would be: {top2}. "
            f"{'There are a few other points to address, but those two will move the needle most.' if n_miss > 2 else ''}"
        ).strip()

    # ── Closing: coaching hint based on depth ────────────────────────────────
    if depth < 35:
        closing = (
            "One structural tip: start with the concept, give a concrete example, "
            "then name one trade-off. That pattern alone will significantly sharpen the answer."
        )
    elif depth < 60:
        closing = (
            "Adding a trade-off or a specific implementation detail would push this "
            "from solid to impressive."
        )
    else:
        closing = (
            "The level of detail and reasoning is strong — "
            "keep anchoring answers in real project experience like this."
        )

    return f"{opening} {middle} {closing}"
