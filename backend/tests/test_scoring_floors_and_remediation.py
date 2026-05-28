"""
Phase 5 — Scoring Floors and Remediation Quality tests

Verifies that:
  1. Completely wrong but substantive answers score in the 15-25 range (not near-zero).
  2. Partial-understanding answers score at least 35.
  3. Remediation follow-ups generate SIMPLER foundational questions, not harder tech probes.
  4. _add_rubric_scores() graduated floor logic is consistent.
  5. followup_generator bypasses deep-tech patterns for remediation decisions.

Background: prior to Phase 5, _add_rubric_scores() applied a flat floor of 30 for
≥15-word answers regardless of coverage. This over-rewarded wrong verbose answers and
under-rewarded short partial ones. followup_generator would scan "JWT" in a weak auth
answer and return a harder revocation question — the opposite of what remediation needs.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.interview import EvaluateAnswerRequest, EvaluationResult
from agents.evaluator_agent import _add_rubric_scores
from services.followup_generator import generate_followup, _remediation_followup


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_eval_req(answer: str, expected_points=None, question_type: str = "technical_concept") -> EvaluateAnswerRequest:
    return EvaluateAnswerRequest(
        session_id="test-session",
        question_id="test-q-001",
        question="Explain the topic",
        answer=answer,
        expected_points=expected_points or ["concept A", "concept B", "concept C"],
        question_type=question_type,
        topic="Test Topic",
    )


def _make_low_result(covered: list = None, technical: int = 5) -> EvaluationResult:
    """Simulate a rule-based result for a weak/wrong answer."""
    return EvaluationResult(
        technical_score=technical,
        depth_score=10,
        correctness_score=5,
        covered_points=covered or [],
        missing_points=["concept A", "concept B", "concept C"],
        feedback="Very weak answer.",
        evaluation_mode="rule_based",
        evaluation_provider="rule_based",
        evaluation_source_label="Rule-based evaluation",
    )


# ═════════════════════════════════════════════════════════════════════════════
# Section 1 — Scoring floors in _add_rubric_scores()
# ═════════════════════════════════════════════════════════════════════════════

class TestScoringFloors:

    def test_empty_answer_scores_zero(self):
        """Empty answer must score 0 — no floor applies."""
        req = _make_eval_req("")
        result = _make_low_result(technical=0)
        enriched = _add_rubric_scores(result, req)
        assert enriched.technical_score == 0, (
            f"Empty answer should score 0, got {enriched.technical_score}"
        )

    def test_wrong_answer_8_words_floors_at_15(self):
        """
        8-word answer with no concept coverage should score at least 15.
        Before Phase 5 this scored as low as 5.
        """
        answer = "I think it has something to do with data."
        req = _make_eval_req(answer)
        result = _make_low_result(covered=[], technical=5)
        enriched = _add_rubric_scores(result, req)
        assert enriched.technical_score >= 15, (
            f"8-word wrong answer should score ≥15, got {enriched.technical_score}"
        )

    def test_wrong_answer_15_words_floors_at_20(self):
        """
        15+ word answer with no concept coverage should score at least 20.
        This represents a completely wrong but verbose attempt.
        """
        answer = (
            "I believe the system works by processing data in some sequential manner "
            "that helps improve overall performance in applications."
        )
        assert len(answer.split()) >= 15
        req = _make_eval_req(answer)
        result = _make_low_result(covered=[], technical=5)
        enriched = _add_rubric_scores(result, req)
        assert enriched.technical_score >= 20, (
            f"15+-word wrong answer should score ≥20, got {enriched.technical_score}"
        )

    def test_partial_answer_floors_at_35(self):
        """
        An answer that covers at least one expected concept should score ≥ 35.
        Partial understanding should never be penalised below 35.
        """
        answer = "I understand concept A involves structured data processing."
        req = _make_eval_req(answer)
        # Simulate: one concept covered, two missing
        result = _make_low_result(covered=["concept A"], technical=25)
        enriched = _add_rubric_scores(result, req)
        assert enriched.technical_score >= 35, (
            f"Partial answer (1 concept covered) should score ≥35, got {enriched.technical_score}"
        )

    def test_partial_answer_two_concepts_floors_at_35(self):
        """
        Covering 2 of 3 expected concepts should score ≥ 35 (ideally much higher).
        """
        answer = (
            "Concept A involves structured data processing, while concept B handles "
            "the asynchronous communication between components."
        )
        req = _make_eval_req(answer)
        result = _make_low_result(covered=["concept A", "concept B"], technical=40)
        enriched = _add_rubric_scores(result, req)
        assert enriched.technical_score >= 35, (
            f"2-concept partial answer should score ≥35, got {enriched.technical_score}"
        )

    def test_short_wrong_answer_under_8_words_not_floored_at_15(self):
        """
        Very short answer (≤ 7 words) with no coverage must NOT be auto-floored.
        "I don't know" should not get 15 points.
        """
        answer = "I don't know this topic"
        assert len(answer.split()) <= 6
        req = _make_eval_req(answer)
        result = _make_low_result(covered=[], technical=5)
        enriched = _add_rubric_scores(result, req)
        # Should remain low — we do NOT guarantee a floor below 8 words
        # (the 7-word cap in _rule_evaluate already handles this)
        assert enriched.technical_score < 35, (
            f"5-word non-answer should not get 35+, got {enriched.technical_score}"
        )

    def test_wrong_answer_does_not_score_above_30_via_floors_alone(self):
        """
        The floors should not inflate a completely wrong answer beyond ~25.
        (The formula may give higher, but the floor alone should not push it above 30.)
        """
        answer = "The system processes information using various algorithms and methods."
        req = _make_eval_req(answer)
        result = _make_low_result(covered=[], technical=5)
        enriched = _add_rubric_scores(result, req)
        # Floor is 20 for ≥15 words. After rubric blend with a low rubric_total,
        # the result should be in the 15-30 range, not ≥35.
        assert enriched.technical_score < 35, (
            f"Wrong verbose answer floor should not exceed ~30; got {enriched.technical_score}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Section 2 — Remediation follow-up quality
# ═════════════════════════════════════════════════════════════════════════════

class TestRemediationFollowupQuality:

    def test_remediation_with_jwt_mention_skips_deep_jwt_probe(self):
        """
        BAD: candidate fumbles auth → system sees "JWT" → asks about revocation strategy.
        GOOD: returns simpler foundational question about the missing concept.

        When decision_type='remediation', the tech-pattern scan must be bypassed.
        """
        answer = (
            "I used JWT for authentication. The server sends a token and the client "
            "stores it somewhere. It makes the user stay logged in."
        )
        missing = ["token flow", "refresh strategy", "secure storage"]
        result = generate_followup(
            answer=answer,
            current_topic="Authentication",
            missing_concepts=missing,
            decision_type="remediation",
            decision_reason="Candidate gave superficial auth answer — probe fundamentals.",
        )
        assert result is not None, "Remediation followup should return a question"
        question, reason, points = result

        # Must NOT be the deep JWT revocation question
        assert "revok" not in question.lower(), (
            "Remediation should not ask about JWT revocation — too advanced. "
            f"Got: {question}"
        )
        assert "stateless" not in question.lower(), (
            "Remediation should not ask about JWT statelessness trade-offs. "
            f"Got: {question}"
        )
        # Should be a simpler 'explain what X means' question
        assert any(
            phrase in question.lower()
            for phrase in ["explain", "own words", "basic", "simple", "step back"]
        ), (
            f"Remediation question should use simpler framing. Got: {question}"
        )

    def test_strengthen_fundamentals_with_redis_mention_skips_deep_probe(self):
        """
        When decision_type='strengthen_fundamentals', a Redis mention must not
        trigger the deep Redis cache invalidation question.
        """
        answer = (
            "I used Redis to cache some data in my project. It was faster than "
            "hitting the database every time."
        )
        missing = ["TTL vs event-driven invalidation", "cache-aside pattern"]
        result = generate_followup(
            answer=answer,
            current_topic="Caching",
            missing_concepts=missing,
            decision_type="strengthen_fundamentals",
        )
        assert result is not None
        question, reason, points = result

        # Must NOT ask the deep Redis cache-invalidation / Sorted Sets probe
        assert "sorted set" not in question.lower(), (
            f"strengthen_fundamentals should not ask about Redis Sorted Sets: {question}"
        )
        assert "cluster mode" not in question.lower(), (
            f"strengthen_fundamentals should not ask about Redis cluster mode: {question}"
        )
        # Should probe fundamentals
        assert any(
            phrase in question.lower()
            for phrase in ["explain", "own words", "basic", "step back", "simple"]
        ), f"Question should be fundamentals-level. Got: {question}"

    def test_remediation_question_targets_first_missing_concept(self):
        """
        _remediation_followup() should ask about the FIRST missing concept,
        not randomly select or ask about all of them simultaneously.
        """
        missing = ["gradient boosting", "learning rate", "tree depth"]
        result = _remediation_followup(missing, "Model Selection")
        assert result is not None
        question, reason, points = result

        # First concept should appear in the question
        assert "gradient boosting" in question.lower(), (
            f"Remediation question should target first missing concept. Got: {question}"
        )

    def test_remediation_followup_has_simpler_framing(self):
        """
        _remediation_followup() questions must use plain, accessible language.
        They must NOT ask about 'production scenarios' (that's for deeper probes).
        """
        missing = ["statelessness", "HTTP verbs"]
        result = _remediation_followup(missing, "REST Fundamentals")
        assert result is not None
        question, reason, points = result

        assert "production scenario" not in question.lower(), (
            f"Remediation must not ask about production scenarios: {question}"
        )
        assert "own words" in question.lower() or "step back" in question.lower(), (
            f"Remediation should use plain-language framing: {question}"
        )

    def test_remediation_returns_none_when_no_missing_concepts(self):
        """
        When there are no missing concepts and decision_type=remediation,
        generate_followup must return None (let question_generator handle it).
        """
        answer = "I have covered all the relevant concepts thoroughly."
        result = generate_followup(
            answer=answer,
            current_topic="Authentication",
            missing_concepts=[],
            decision_type="remediation",
        )
        assert result is None, (
            "Remediation with no missing concepts should return None"
        )

    def test_normal_deeper_followup_still_uses_tech_patterns(self):
        """
        When decision_type='deeper_follow_up' (not remediation), the JWT deep
        probe SHOULD fire — the tech-pattern bypass must not affect normal probing.
        """
        answer = (
            "I implemented JWT authentication where the server issues a token "
            "and the client stores it in localStorage."
        )
        result = generate_followup(
            answer=answer,
            current_topic="Authentication",
            missing_concepts=["revocation strategy"],
            decision_type="deeper_follow_up",
        )
        assert result is not None, "deeper_follow_up should return a tech probe for JWT"
        question, _, _ = result
        # Should trigger the JWT-specific follow-up about stateless revocation
        assert "jwt" in question.lower() or "revok" in question.lower() or "stateless" in question.lower(), (
            f"deeper_follow_up should ask the JWT deep probe. Got: {question}"
        )

    def test_remediation_reason_mentions_fundamentals(self):
        """
        The reason field returned by _remediation_followup must mention
        fundamentals or basics — this ensures UI/logging shows correct intent.
        """
        missing = ["token flow", "refresh strategy"]
        result = _remediation_followup(missing, "Authentication")
        assert result is not None
        _, reason, _ = result
        assert any(
            word in reason.lower()
            for word in ["fundamental", "basic", "conceptual", "foundation"]
        ), f"Remediation reason should reference fundamentals. Got: {reason}"

    def test_remediation_points_include_definition_and_example(self):
        """
        _remediation_followup() expected_points must include definition and
        example expectations — not production/trade-off depth.
        """
        missing = ["statelessness"]
        result = _remediation_followup(missing, "REST Fundamentals")
        assert result is not None
        _, _, points = result
        point_text = " ".join(points).lower()
        assert "definition" in point_text or "explain" in point_text or "what" in point_text, (
            f"Remediation points should include definition expectation. Got: {points}"
        )
        assert "example" in point_text or "concrete" in point_text, (
            f"Remediation points should include example expectation. Got: {points}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Section 3 — _rule_evaluate() floor for 8+ word answers
# ═════════════════════════════════════════════════════════════════════════════

class TestRuleEvaluateFloor:

    def test_rule_evaluate_8_word_answer_scores_at_least_15(self):
        """
        _rule_evaluate() must produce technical_score ≥ 15 for any answer
        with 8+ words, even if the answer covers no expected concepts.
        """
        from agents.evaluator_agent import _rule_evaluate

        req = EvaluateAnswerRequest(
            session_id="test-session",
            question_id="test-q-floor-1",
            question="Explain gradient boosting",
            answer="I think it uses some kind of tree structure for predictions",
            expected_points=["boosting ensemble", "gradient descent", "loss function", "weak learners"],
            question_type="technical_concept",
            topic="Model Selection",
        )
        assert len(req.answer.split()) >= 8
        result = _rule_evaluate(req)
        assert result.technical_score >= 15, (
            f"8+-word answer should score ≥15, got {result.technical_score}"
        )

    def test_rule_evaluate_very_short_wrong_answer_can_score_below_15(self):
        """
        A ≤6-word answer with no coverage may still score below 15.
        The floor only protects substantive attempts.
        """
        from agents.evaluator_agent import _rule_evaluate

        req = EvaluateAnswerRequest(
            session_id="test-session",
            question_id="test-q-floor-2",
            question="Explain gradient boosting",
            answer="I don't know",
            expected_points=["boosting", "gradient descent", "loss function"],
            question_type="technical_concept",
            topic="Model Selection",
        )
        assert len(req.answer.split()) <= 4
        result = _rule_evaluate(req)
        # The 6-word cap applies: score should be very low
        assert result.technical_score <= 15, (
            f"Very short non-answer should score ≤15, got {result.technical_score}"
        )
