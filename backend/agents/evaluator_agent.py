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
    if not settings.use_llm or not settings.anthropic_api_key:
        return None

    try:
        import anthropic

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

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
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
        )

    except Exception as exc:
        logger.warning("LLM evaluation failed, falling back to rule-based: %s", exc)
        return None


# ── Rule-based path ───────────────────────────────────────────────────────────

def _rule_evaluate(req: EvaluateAnswerRequest) -> EvaluationResult:
    ratio, covered, missing = sc.keyword_coverage(req.answer, req.expected_points)
    depth = sc.depth_score(req.answer)
    correctness = sc.correctness_score(ratio)
    technical = sc.technical_score_rule_based(ratio, depth)
    feedback = sc.generate_feedback(covered, missing, technical, depth)

    return EvaluationResult(
        technical_score=technical,
        depth_score=depth,
        correctness_score=correctness,
        covered_points=covered,
        missing_points=missing,
        feedback=feedback,
    )


def _add_rubric_scores(result: EvaluationResult, req: EvaluateAnswerRequest) -> EvaluationResult:
    """
    Phase 11: Enrich an EvaluationResult with rubric-based scores.
    Topic is extracted from the question text heuristically when not directly available.
    Always falls back gracefully if topic cannot be determined.
    """
    try:
        # Infer topic from the request if possible
        topic = getattr(req, "topic", None) or ""
        rubric_data = rubric.score_with_rubric(req.answer, topic, req.expected_points)
        return result.model_copy(update={
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
