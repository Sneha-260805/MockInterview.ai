"""
Answer evaluator. Rule-based by default; upgrades to LLM when USE_LLM=true.

Rule-based path:
  technical  = coverage × 0.7 + depth × 0.3
  depth      = word-count heuristic + structural-signal bonus
  correctness= coverage → score mapping

LLM path:
  technical  = semantic_score × 0.7 + coverage × 0.3
  depth/correctness come from Claude's assessment directly.
  covered/missing points come from Claude; keyword pass fills any gaps.
"""

import json
import logging
import re

from models.interview import EvaluateAnswerRequest, EvaluationResult
from services import scoring_service as sc
from services import rubric_service as rubric

logger = logging.getLogger(__name__)


# ── LLM path ─────────────────────────────────────────────────────────────────

async def _llm_evaluate(req: EvaluateAnswerRequest) -> EvaluationResult | None:
    from config import get_settings
    settings = get_settings()
    if not settings.use_llm or (not settings.anthropic_api_key and not settings.gemini_api_key):
        return None
    provider = (
        "gemini"
        if settings.llm_provider.lower() == "gemini" and settings.gemini_api_key
        else "anthropic"
        if settings.anthropic_api_key
        else settings.llm_provider.lower()
    )

    try:
        from services.llm_client import call_llm

        prompt = (
            "You are an expert technical interviewer evaluating a candidate's answer.\n\n"
            f"Question: {req.question}\n"
            f"Expected points to cover: {json.dumps(req.expected_points)}\n"
            f"Candidate's answer: \"{req.answer}\"\n\n"
            "Evaluate objectively and return ONLY valid JSON — no markdown, no prose:\n"
            "{\n"
            '  "semantic_score": <integer 0-100, overall semantic quality>,\n'
            '  "depth_score": <integer 0-100, how detailed and structured>,\n'
            '  "correctness_score": <integer 0-100, technical accuracy>,\n'
            '  "covered_points": [<exact strings from expected_points that were addressed>],\n'
            '  "missing_points": [<exact strings from expected_points that were NOT addressed>],\n'
            '  "feedback": "<2-3 sentences of constructive, specific feedback>"\n'
            "}\n\n"
            "For covered_points and missing_points use the EXACT strings from the expected_points list."
        )

        raw = await call_llm(prompt, max_tokens=600)
        if raw is None:
            return None
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None

        data = json.loads(m.group(0))

        # Validate covered/missing against actual expected_points list
        valid = set(req.expected_points)
        llm_covered = [p for p in data.get("covered_points", []) if p in valid]
        llm_missing = [p for p in data.get("missing_points", []) if p in valid]

        # Fill any unclassified points using keyword fallback
        classified = set(llm_covered) | set(llm_missing)
        unclassified = [p for p in req.expected_points if p not in classified]
        if unclassified:
            _, kw_cov, kw_miss = sc.keyword_coverage(req.answer, unclassified)
            llm_covered += kw_cov
            llm_missing += kw_miss

        coverage_ratio = len(llm_covered) / max(len(req.expected_points), 1)
        semantic = int(data.get("semantic_score", 50))
        tech = sc.technical_score_with_llm(semantic, coverage_ratio)

        return EvaluationResult(
            technical_score=tech,
            depth_score=int(data.get("depth_score", sc.depth_score(req.answer))),
            correctness_score=int(data.get("correctness_score", sc.correctness_score(coverage_ratio))),
            covered_points=llm_covered,
            missing_points=llm_missing,
            feedback=data.get("feedback", ""),
            evaluation_mode="ai",
            evaluation_provider=provider,
            evaluation_source_label=f"AI evaluation ({provider})",
        )

    except Exception as exc:
        logger.warning("LLM evaluation failed, falling back to rule-based: %s", exc)
        return None


# ── Rule-based path ───────────────────────────────────────────────────────────

def _rule_evaluate(req: EvaluateAnswerRequest) -> EvaluationResult:
    """
    Competence-first evaluation.

    Design philosophy — behave like a realistic technical interviewer:
      • Depth of reasoning carries more weight than checklist completeness.
      • A candidate who clearly understands a topic but missed one rubric point
        should not be penalised heavily.
      • Strong positive signals (trade-offs, examples, personal experience,
        metrics) are rewarded explicitly via competence floors.
      • Semantic similarity is used as a bonus modifier, not a primary driver
        (TF-IDF cosine is naturally low for paraphrased answers).

    Pipeline:
      1. Semantic coverage  → coverage ratio + covered/missing lists
      2. depth_level()      → reasoning quality score 0–100 + signal list
      3. Base technical     = depth × 0.60 + coverage × 0.40   (depth-led)
      4. Semantic modifier  = doc_sim × 15   (max +15 bonus, never a penalty)
      5. Competence floors  keyed on (signal count × coverage ratio)
    """
    answer_words = req.answer.split()
    if not req.answer.strip():
        return EvaluationResult(
            technical_score=0,
            depth_score=0,
            correctness_score=0,
            covered_points=[],
            missing_points=req.expected_points,
            feedback="No answer was provided, so there is not enough evidence to assess technical understanding.",
            evaluation_mode="rule_based",
            evaluation_provider="rule_based",
            evaluation_source_label="Rule-based evaluation",
        )

    try:
        from services import semantic_scorer as sem

        # Per-concept semantic coverage
        ratio, covered, missing = sem.semantic_coverage(req.answer, req.expected_points)

        # Document-level similarity — used only as a small bonus modifier
        reference_text = ". ".join(req.expected_points) if req.expected_points else ""
        doc_sim = sem.semantic_similarity(req.answer, reference_text) if reference_text else 0.0

        # Depth / reasoning quality — the primary technical signal
        _depth_level, depth, signals = sem.depth_level(req.answer)

        # ── Coverage-based depth floor ───────────────────────────────────────
        # A candidate who correctly covers 80% of expected concepts KNOWS the
        # material, even if they didn't use explicit discourse markers (because,
        # however, for example). Give them minimum depth credit for that knowledge.
        # Formula: 100% coverage → at least 50 depth, 50% → at least 25.
        #
        # Guard: only apply for answers ≥ 45 words.  Short and shallow answers
        # inflate coverage artificially via synonym expansion — a 40-word answer
        # that names "jwt, token, sessions" should not get depth credit for high
        # coverage when it contains zero reasoning.  A 45-word substantive answer
        # with real concept explanation is a different signal entirely.
        if len(req.answer.split()) >= 45:
            depth = max(depth, round(ratio * 50))

        # ── Base technical: depth-led, coverage-supported ───────────────────
        coverage_score = round(ratio * 100)
        technical = round(depth * 0.60 + coverage_score * 0.40)

        # Semantic similarity as a pure upside modifier (max +15, never negative)
        semantic_boost = round(min(doc_sim * 100, 100) * 0.15)
        technical = min(100, technical + semantic_boost)

        # ── Competence floors (interviewer realism) ─────────────────────────
        # Map (signal_count × coverage) to minimum realistic interviewer scores.
        # Floors only apply when there is evidence of genuine understanding — they
        # do NOT trigger on signals alone without some concept coverage (ratio gate).
        n_signals = len(signals)
        if n_signals >= 4 and ratio >= 0.30:
            technical = max(technical, 76)   # expert reasoning + solid coverage
        elif n_signals >= 3 and ratio >= 0.25:
            technical = max(technical, 78)   # strong reasoning + strong coverage
        elif n_signals >= 2 and ratio >= 0.50:
            technical = max(technical, 65)   # decent reasoning + solid coverage
        elif n_signals >= 2 and ratio >= 0.20:
            technical = max(technical, 55)   # structured reasoning + some coverage
        elif n_signals >= 1 and ratio >= 0.60:
            technical = max(technical, 63)   # some reasoning + comprehensive coverage
        elif n_signals >= 1 and ratio >= 0.10:
            technical = max(technical, 42)   # minimal structure present

        correctness = sc.correctness_score(ratio)
        technical = max(5, min(100, technical))
        if not covered and len(answer_words) <= 6:
            technical = min(technical, 7)
            correctness = min(correctness, 5)
            depth = min(depth, 5)

    except Exception as exc:
        logger.warning("Semantic scoring failed, falling back to keyword: %s", exc)
        ratio, covered, missing = sc.keyword_coverage(req.answer, req.expected_points)
        depth = sc.depth_score(req.answer)
        signals = []
        correctness = sc.correctness_score(ratio)
        technical = sc.technical_score_rule_based(ratio, depth)
        if not covered and len(answer_words) <= 6:
            technical = min(technical, 7)
            correctness = min(correctness, 5)
            depth = min(depth, 5)

    feedback = sc.generate_feedback(covered, missing, technical, depth)

    return EvaluationResult(
        technical_score=technical,
        depth_score=depth,
        correctness_score=correctness,
        covered_points=covered,
        missing_points=missing,
        feedback=feedback,
        evaluation_mode="rule_based",
        evaluation_provider="rule_based",
        evaluation_source_label="Rule-based evaluation",
    )


def _add_rubric_scores(result: EvaluationResult, req: EvaluateAnswerRequest) -> EvaluationResult:
    """
    Enrich an EvaluationResult with rubric-based scores AND blend rubric_total
    into technical_score using an asymmetric formula:

    Asymmetric rubric blend:
      • When rubric_total ≥ technical_score:
          blended = technical×0.55 + rubric×0.45   — rubric provides strong evidence boost
      • When rubric_total < technical_score:
          blended = technical×0.85 + rubric×0.15   — rubric slightly anchors, doesn't punish

    Rationale: A candidate who demonstrated deep reasoning (high technical from depth signals)
    but didn't surface specific rubric keywords should NOT be penalised for that mismatch.
    Conversely, a keyword-heavy answer with weak depth SHOULD see its score improved by rubric.
    """
    if not req.answer.strip():
        return result
    try:
        topic = getattr(req, "topic", None) or ""
        rubric_data = rubric.score_with_rubric(req.answer, topic, req.expected_points)

        rt = rubric_data["rubric_total"]
        ts = result.technical_score

        # Asymmetric blend: rubric enriches upward, barely drags downward
        if rt >= ts:
            blended_tech = round(ts * 0.55 + rt * 0.45)
        else:
            blended_tech = round(ts * 0.85 + rt * 0.15)

        blended_tech = max(5, min(100, blended_tech))

        # Global floor: any substantive attempt (≥ 15 words) shouldn't score below 30.
        # Prevents rubric vocabulary variation across topics from producing implausibly
        # low scores for answers that are genuinely weak but not empty.
        if len(req.answer.split()) >= 15:
            blended_tech = max(blended_tech, 30)

        return result.model_copy(update={
            "technical_score":        blended_tech,
            "rubric_scores":          rubric_data["rubric_scores"],
            "rubric_total":           rubric_data["rubric_total"],
            "evidence":               rubric_data["evidence"],
            "improvement_hint":       rubric_data["improvement_hint"],
            "interviewer_diagnosis":  rubric_data["interviewer_diagnosis"],
        })
    except Exception as exc:
        logger.warning("Rubric scoring failed (non-fatal): %s", exc)
        return result


# ── Public API ────────────────────────────────────────────────────────────────

async def evaluate(req: EvaluateAnswerRequest) -> EvaluationResult:
    result = await _llm_evaluate(req)
    if result is None:
        result = _rule_evaluate(req)
    # Phase 11: always enrich with rubric scores
    result = _add_rubric_scores(result, req)
    return result
