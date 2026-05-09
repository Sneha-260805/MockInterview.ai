"""
Semantic scoring service — lightweight, deterministic, zero extra dependencies.

Uses a pure-Python TF-IDF cosine similarity to measure how well a candidate's
answer covers the expected concepts, going beyond simple keyword matching.

Three public functions:
  semantic_similarity(answer, reference)  → 0.0-1.0 cosine score
  semantic_coverage(answer, expected)     → (ratio, covered, missing)
  depth_level(answer)                     → (level_str, 0-100 score, signals)
  combined_technical_score(...)           → 0-100 blended technical score
"""

import re
import math
from typing import List, Tuple, Dict

# ── Stopwords ──────────────────────────────────────────────────────────────────

_STOP: set = {
    "a", "an", "the", "and", "or", "of", "in", "to", "for", "with",
    "is", "be", "by", "on", "at", "as", "from", "it", "its", "use",
    "how", "what", "when", "where", "which", "that", "this", "are",
    "you", "i", "we", "they", "he", "she", "was", "were", "had",
    "has", "have", "can", "could", "would", "should", "will", "do",
    "did", "does", "not", "so", "but", "if", "then", "just", "about",
    "also", "more", "very", "like", "any", "some", "our", "your",
    "my", "their", "its", "into", "than", "over", "after", "before",
}

# ── Technical depth vocabulary ─────────────────────────────────────────────────
# Presence of these signals expert-level thinking.

_DEPTH_VOCAB: frozenset = frozenset({
    "algorithm", "complexity", "o(n)", "latency", "throughput", "bottleneck",
    "race condition", "deadlock", "consistency", "partition", "sharding",
    "replication", "eventual consistency", "idempotent", "idempotency",
    "linearizability", "serializability", "isolation level", "atomicity",
    "durability", "fault tolerance", "circuit breaker", "backpressure",
    "watermark", "checkpoint", "saga", "two-phase commit", "raft", "paxos",
    "gossip protocol", "bloom filter", "merkle tree", "crdt", "ot",
    "horizontal scaling", "vertical scaling", "cap theorem", "base theorem",
    "eventual consistency", "strong consistency", "causal consistency",
    "quorum", "replication factor", "compaction", "bloom filter",
    "gradient descent", "backpropagation", "attention mechanism",
    "regularisation", "regularization", "hyperparameter", "overfitting",
    "underfitting", "bias variance", "cross validation", "confusion matrix",
    "precision recall", "auc roc", "f1 score",
})


# ── Tokenization ───────────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return [t for t in text.split() if t not in _STOP and len(t) >= 2]


# ── TF-IDF cosine similarity ───────────────────────────────────────────────────

def _tf_vector(tokens: List[str], vocab: Dict[str, int]) -> List[float]:
    from collections import Counter
    counts = Counter(tokens)
    total = max(len(tokens), 1)
    vec = [0.0] * len(vocab)
    for term, idx in vocab.items():
        vec[idx] = counts.get(term, 0) / total
    return vec


def _cosine(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    m1 = math.sqrt(sum(a * a for a in v1))
    m2 = math.sqrt(sum(b * b for b in v2))
    if m1 == 0 or m2 == 0:
        return 0.0
    return min(1.0, dot / (m1 * m2))


def semantic_similarity(answer: str, reference: str) -> float:
    """
    TF-IDF cosine similarity between answer and reference text.
    Returns 0.0 – 1.0.  Pure Python, no external dependencies.
    """
    a_tok = _tokenize(answer)
    r_tok = _tokenize(reference)
    if not a_tok or not r_tok:
        return 0.0
    vocab = {t: i for i, t in enumerate(set(a_tok + r_tok))}
    v1 = _tf_vector(a_tok, vocab)
    v2 = _tf_vector(r_tok, vocab)
    return _cosine(v1, v2)


# ── Per-concept coverage ───────────────────────────────────────────────────────

def _keyword_hit(answer_lower: str, point: str) -> bool:
    """Lightweight keyword check as a fallback / complement to cosine sim."""
    words = _tokenize(point)
    hits = sum(
        1 for w in words
        if w in answer_lower or (len(w) >= 5 and w[:5] in answer_lower)
    )
    return hits >= max(1, len(words) // 2)


def semantic_coverage(
    answer: str,
    expected_points: List[str],
) -> Tuple[float, List[str], List[str]]:
    """
    Check each expected_point for semantic presence in the answer.

    A point is "covered" when EITHER:
      • TF-IDF cosine similarity ≥ 0.12  (semantic overlap), OR
      • Keyword heuristic hits ≥ 50% of content words (robust to paraphrasing)

    Returns (coverage_ratio, covered_list, missing_list).
    """
    if not expected_points:
        return 0.0, [], []

    answer_lower = answer.lower()
    covered: List[str] = []
    missing: List[str] = []

    for point in expected_points:
        sim = semantic_similarity(answer, point)
        kw = _keyword_hit(answer_lower, point)
        if sim >= 0.12 or kw:
            covered.append(point)
        else:
            missing.append(point)

    ratio = len(covered) / len(expected_points)
    return ratio, covered, missing


# ── Depth estimation ───────────────────────────────────────────────────────────

def depth_level(answer: str) -> Tuple[str, int, List[str]]:
    """
    Estimate how deeply an answer demonstrates understanding.

    Returns:
      level   — "beginner" | "intermediate" | "deep"
      score   — 0-100
      signals — list of matched depth indicators (for explanation)

    Scoring signals (additive):
      Causal reasoning          +15
      Trade-off discussion      +20
      Concrete examples         +15
      Quantitative metrics      +15
      Structured sequence       +10
      Advanced tech vocabulary  +20 / +10
      Personal experience        +10
      Word-count baseline        ±5
    """
    al = answer.lower()
    signals: List[str] = []
    score = 0

    if re.search(r"\b(because|therefore|since|as a result|this means|which means|consequently)\b", al):
        signals.append("causal reasoning")
        score += 15

    if re.search(
        r"\b(trade.?off|however|alternatively|on the other hand|advantage|disadvantage|pros|cons|whereas|but consider)\b",
        al,
    ):
        signals.append("trade-off discussion")
        score += 20

    if re.search(
        r"\b(for example|such as|specifically|to illustrate|in practice|for instance|take .{0,20} as an example)\b",
        al,
    ):
        signals.append("concrete example")
        score += 15

    if re.search(
        r"\b\d+[-\s]*(?:ms|milliseconds?|seconds?|minutes?|hours?|days?|weeks?|%|percent|kb|mb|gb|tb|x\b|requests?|queries?|nodes?|instances?|concurrent|tps|qps|rps|users?|services?)\b",
        al,
    ):
        signals.append("quantitative metric")
        score += 15

    if re.search(r"\b(first(ly)?|second(ly)?|third(ly)?|then|next|finally|step\s*\d)\b", al):
        signals.append("structured sequence")
        score += 10

    vocab_hits = [kw for kw in _DEPTH_VOCAB if kw in al]
    if len(vocab_hits) >= 2:
        signals.append("advanced technical vocabulary")
        score += 20
    elif vocab_hits:
        signals.append("technical vocabulary")
        score += 10

    if re.search(
        r"\b(i (built|implemented|used|chose|designed|faced|encountered|deployed|configured|went with|picked|opted)|"
        r"we (used|built|decided|switched|migrated|chose|picked|opted|went with|deployed|implemented))\b",
        al,
    ):
        signals.append("personal experience")
        score += 10

    word_count = len(answer.split())
    if word_count < 30:
        score = max(5, score - 15)
    elif word_count >= 120:
        score = min(100, score + 5)

    score = max(5, min(100, score))
    if score >= 65:
        level = "deep"
    elif score >= 35:
        level = "intermediate"
    else:
        level = "beginner"

    return level, score, signals


# ── Combined technical score ───────────────────────────────────────────────────

def combined_technical_score(
    semantic_sim: float,
    coverage_ratio: float,
    depth_sc: int,
    rubric_total: int,
) -> int:
    """
    Blend all evaluation signals into a single 0-100 technical score.

    Weights (sum to 1.0):
      Semantic similarity:  0.25   — captures paraphrased answers
      Concept coverage:     0.30   — how many expected points addressed
      Depth score:          0.20   — structural quality of reasoning
      Rubric total:         0.25   — 5-dimension rubric (conceptual + practical + trade-offs)
    """
    blended = (
        semantic_sim * 100 * 0.25
        + coverage_ratio * 100 * 0.30
        + depth_sc * 0.20
        + rubric_total * 0.25
    )
    return max(5, min(100, round(blended)))
