"""
TASK 7 — Tests for the multimodal intelligence layer.

Covers:
  1. Audio helper functions (_pace_label, _detect_audio_issue,
     _orchestrator_recommendation, _coaching_tip, _audio_reasoning_summary)
  2. Video extras helper (_compute_video_extras)
  3. Role-aware aggregation (_get_weights, aggregate_turn with role=)
  4. Multimodal signal classification (_classify_signal)
  5. Intelligence engine: multimodal_signal → decision_type override
  6. Feedback agent: coaching_tip + audio_reasoning_summary surfaced
  7. Backward compatibility: existing "weights" key + positional callers

All tests are pure-Python (no network, no LLM, no disk I/O required).
"""

import sys
import os

# Allow imports from the backend package root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── 1. Audio helper functions ──────────────────────────────────────────────────

from services.audio_analyzer import (
    _pace_label,
    _detect_audio_issue,
    _orchestrator_recommendation,
    _coaching_tip,
    _audio_reasoning_summary,
    FILLER_RATIO_MOD,
    FILLER_RATIO_HIGH,
    CONFIDENCE_CRITICAL,
    CONFIDENCE_LOW,
    CLARITY_LOW,
    WPM_SLOW_THRESHOLD,
    WPM_FAST_THRESHOLD,
)


class TestPaceLabel:
    def test_good_pace(self):
        assert _pace_label(130, "low", 0.02) == "good_pace"

    def test_slow_with_hesitation(self):
        assert _pace_label(80, "high", 0.03) == "slow_with_hesitation"
        assert _pace_label(80, "moderate", 0.03) == "slow_with_hesitation"

    def test_slow_with_fillers(self):
        assert _pace_label(80, "low", 0.06) == "slow_with_fillers"

    def test_plain_slow(self):
        assert _pace_label(80, "low", 0.02) == "slow"

    def test_fast_rambling(self):
        # > 210 WPM + moderate hesitation
        assert _pace_label(215, "moderate", 0.06) == "fast_rambling"

    def test_fast_with_fillers(self):
        # 175-210 WPM + fillers
        assert _pace_label(180, "low", 0.06) == "fast_with_fillers"

    def test_plain_fast(self):
        assert _pace_label(185, "low", 0.02) == "fast"

    def test_measured_with_hesitation(self):
        assert _pace_label(130, "high", 0.02) == "measured_with_hesitation"

    def test_measured_with_pauses(self):
        assert _pace_label(130, "moderate", 0.02) == "measured_with_pauses"


class TestDetectAudioIssue:
    def test_very_brief_response(self):
        issue = _detect_audio_issue("low", 0.02, 130, 10, "stable", 0)
        assert issue is not None
        assert "brief" in issue.lower()

    def test_high_hesitation_with_pauses(self):
        issue = _detect_audio_issue("high", 0.03, 130, 80, "stable", 5)
        assert issue is not None
        assert "hesitation" in issue.lower() or "pause" in issue.lower()

    def test_excessive_fillers(self):
        issue = _detect_audio_issue("low", 0.15, 130, 80, "stable", 0)
        assert issue is not None
        assert "filler" in issue.lower()

    def test_no_issue_good_answer(self):
        issue = _detect_audio_issue("low", 0.02, 130, 90, "stable", 1)
        assert issue is None

    def test_very_fast_pace(self):
        issue = _detect_audio_issue("low", 0.02, 220, 80, "stable", 0)
        assert issue is not None
        assert "fast" in issue.lower() or "wpm" in issue.lower()

    def test_monotone(self):
        issue = _detect_audio_issue("low", 0.02, 130, 80, "monotone", 0)
        assert issue is not None
        assert "monotone" in issue.lower()

    def test_priority_brevity_over_hesitation(self):
        # word_count < 20 takes priority over high hesitation
        issue = _detect_audio_issue("high", 0.15, 130, 10, "stable", 5)
        assert "brief" in (issue or "").lower()


class TestOrchestratorRecommendation:
    def test_critical_both_low(self):
        rec = _orchestrator_recommendation(30, 40, "high", 50)
        assert rec == "give_encouragement_and_ask_simpler_question"

    def test_low_confidence_high_hesitation(self):
        rec = _orchestrator_recommendation(50, 70, "high", 80)
        assert rec == "reduce_difficulty_and_add_encouragement"

    def test_low_confidence_moderate_hesitation(self):
        rec = _orchestrator_recommendation(50, 70, "moderate", 80)
        assert rec == "monitor_confidence_maintain_difficulty"

    def test_low_clarity_brief(self):
        rec = _orchestrator_recommendation(70, 45, "low", 20)
        assert rec == "ask_for_structured_elaboration"

    def test_low_clarity_adequate_length(self):
        rec = _orchestrator_recommendation(70, 45, "low", 80)
        assert rec == "request_clearer_explanation"

    def test_strong_both(self):
        rec = _orchestrator_recommendation(80, 80, "low", 100)
        assert rec == "increase_difficulty"

    def test_standard_flow(self):
        rec = _orchestrator_recommendation(65, 65, "low", 70)
        assert rec == "continue_standard_flow"


class TestCoachingTip:
    def test_brief_answer_tip(self):
        tip = _coaching_tip("low", 0.02, 130, 70, 10)
        assert tip is not None
        assert "structure" in tip.lower() or "example" in tip.lower()

    def test_high_hesitation_and_fillers(self):
        tip = _coaching_tip("high", 0.08, 130, 70, 80)
        assert tip is not None
        assert "um" in tip.lower() or "silence" in tip.lower()

    def test_very_fast_pace_tip(self):
        tip = _coaching_tip("low", 0.02, 210, 70, 80)
        assert tip is not None
        assert "slow" in tip.lower() or "pace" in tip.lower()

    def test_no_tip_for_good_answer(self):
        # Good pace, low fillers, low hesitation, good clarity
        tip = _coaching_tip("low", 0.02, 130, 75, 100)
        assert tip is None


class TestAudioReasoningSummary:
    def test_well_developed_natural_pace(self):
        summary = _audio_reasoning_summary(130, "low", 0.02, 75, 75, 1, 100)
        assert "confident" in summary.lower() or "clear" in summary.lower()
        assert "100 words" in summary or "well-developed" in summary

    def test_high_hesitation_summary(self):
        summary = _audio_reasoning_summary(85, "high", 0.12, 35, 45, 6, 80)
        assert "hesitation" in summary.lower() or "confidence" in summary.lower()

    def test_brief_response_summary(self):
        summary = _audio_reasoning_summary(120, "low", 0.02, 60, 60, 0, 10)
        assert "brief" in summary.lower()

    def test_returns_string(self):
        summary = _audio_reasoning_summary(130, "low", 0.02, 70, 70, 2, 90)
        assert isinstance(summary, str)
        assert len(summary) > 20


# ── 2. Video extras helper ─────────────────────────────────────────────────────

from services.video_analyzer import _compute_video_extras


class TestComputeVideoExtras:
    def test_none_inputs_return_none_scores(self):
        extras = _compute_video_extras(None, None, None, None, 0.0)
        assert extras["nervousness_proxy_score"] is None
        assert extras["looking_away_proxy_score"] is None
        assert extras["recommendation_to_orchestrator"] == "request_better_video_setup"
        assert isinstance(extras["visual_reasoning_summary"], str)

    def test_high_engagement_low_movement(self):
        extras = _compute_video_extras(80, 80, 70, "low", 0.9)
        assert extras["nervousness_proxy_score"] is not None
        assert extras["nervousness_proxy_score"] < 30     # low nervousness
        assert extras["looking_away_proxy_score"] == 20   # 100 - 80

    def test_low_engagement_high_movement(self):
        extras = _compute_video_extras(35, 35, 40, "high", 0.5)
        assert extras["nervousness_proxy_score"] is not None
        assert extras["nervousness_proxy_score"] >= 35    # elevated nervousness
        assert "acknowledge" in extras["recommendation_to_orchestrator"] or \
               "request" in extras["recommendation_to_orchestrator"]

    def test_looking_away_proxy_is_framing_inversion(self):
        extras = _compute_video_extras(75, 60, 70, "low", 0.85)
        assert extras["looking_away_proxy_score"] == 40   # 100 - 60

    def test_visual_summary_is_string(self):
        extras = _compute_video_extras(70, 70, 60, "medium", 0.8)
        assert isinstance(extras["visual_reasoning_summary"], str)
        assert len(extras["visual_reasoning_summary"]) > 20

    def test_high_nervousness_recommendation(self):
        # nervousness_proxy = 35 (high movement) + framing penalty + engagement penalty
        extras = _compute_video_extras(40, 40, None, "high", 0.5)
        # engagement = 40 → framing_penalty = (50-40)//2 = 5; movement = 35
        assert extras["recommendation_to_orchestrator"] in (
            "acknowledge_nervousness_and_encourage",
            "note_nervousness_monitor_confidence",
            "request_better_video_setup",
        )


# ── 3. Role-aware aggregation ──────────────────────────────────────────────────

from services import multimodal_aggregator
from services.multimodal_aggregator import (
    _get_weights,
    _DEFAULT_WEIGHTS,
    _ROLE_WEIGHTS,
    aggregate_turn,
)


class TestGetWeights:
    def test_backend_developer_heavier_technical(self):
        w, reason = _get_weights("Backend Developer")
        assert w["technical"] == 0.55
        assert "backend" in reason

    def test_product_manager_heavier_communication(self):
        w, reason = _get_weights("Product Manager")
        assert w["communication"] == 0.35
        assert w["technical"] == 0.20

    def test_unknown_role_falls_back_to_defaults(self):
        w, reason = _get_weights("Underwater Basket Weaver")
        assert w == _DEFAULT_WEIGHTS
        assert reason == "default_weights"

    def test_empty_role_falls_back(self):
        w, reason = _get_weights("")
        assert w == _DEFAULT_WEIGHTS

    def test_case_insensitive(self):
        w1, _ = _get_weights("backend developer")
        w2, _ = _get_weights("BACKEND DEVELOPER")
        assert w1 == w2 == _ROLE_WEIGHTS["backend developer"]

    def test_all_weights_sum_to_one(self):
        for role, w in _ROLE_WEIGHTS.items():
            total = sum(w.values())
            assert abs(total - 1.0) < 0.001, f"Weights for '{role}' do not sum to 1.0: {total}"


class TestAggregateWithRole:
    def test_backend_developer_uses_higher_technical_weight(self):
        evaluation = {"technical_score": 90, "depth_score": 80}
        result_backend  = aggregate_turn(evaluation, role="Backend Developer")
        result_pm       = aggregate_turn(evaluation, role="Product Manager")
        # Backend weights tech more → higher combined for same tech score
        assert result_backend["combined_score"] > result_pm["combined_score"]

    def test_backward_compat_weights_key_present(self):
        """Existing tests check result["weights"]["technical"] == 0.45 with no role."""
        result = aggregate_turn(
            {"technical_score": 80, "depth_score": 70},
            {"communication_clarity_score": 75, "confidence_score": 70,
             "pause_count": 1, "hesitation_count": 1},
            {"engagement_score": 65, "posture_score": 70, "stress_indicator": "medium"},
            role_fit_score=90,
        )
        assert result["weights"]["technical"] == 0.45
        assert 0 <= result["combined_score"] <= 100
        assert result["source"] == "multimodal"
        assert result["evidence"]

    def test_new_keys_present(self):
        result = aggregate_turn({"technical_score": 70, "depth_score": 60})
        assert "weights_used" in result
        assert "reason" in result
        assert "multimodal_signal" in result

    def test_role_keyword_only(self):
        """role must be keyword-only — existing positional callers not broken."""
        result = aggregate_turn({"technical_score": 80, "depth_score": 70}, None, None, 70)
        assert result["combined_score"] >= 0


# ── 4. Signal classification ───────────────────────────────────────────────────

from services.multimodal_aggregator import _classify_signal


class TestClassifySignal:
    def test_strong_technical_low_confidence(self):
        signal = _classify_signal(80, 45, 70, 65)
        assert signal == "strong_technical_low_confidence"

    def test_weak_technical_low_confidence_low_comm(self):
        signal = _classify_signal(40, 40, 40, 50)
        assert signal == "weak_technical_low_confidence"

    def test_strong_candidate(self):
        signal = _classify_signal(80, 70, 70, 65)
        assert signal == "strong_candidate"

    def test_confidence_and_engagement_low(self):
        signal = _classify_signal(65, 45, 65, 40)
        assert signal == "confidence_and_engagement_low"

    def test_communication_needs_improvement(self):
        signal = _classify_signal(65, 65, 40, 65)
        assert signal == "communication_needs_improvement"

    def test_confidence_low(self):
        signal = _classify_signal(65, 45, 65, 65)
        assert signal == "confidence_low"

    def test_average_performance(self):
        signal = _classify_signal(60, 60, 60, 60)
        assert signal == "average_performance"

    def test_strong_technical(self):
        # comm=60 (<65 threshold) prevents "strong_candidate"; tech strong, conf OK → "strong_technical"
        signal = _classify_signal(75, 65, 60, 65)
        assert signal == "strong_technical"


# ── 5. Intelligence engine: signal → decision override ────────────────────────

from models.agent_state import CandidateState, AgentDecisionTrace, InterviewPlanItem
from agents.intelligence_engine import make_next_question_decision


def _make_state(**kwargs):
    defaults = dict(
        session_id="s1",
        candidate_id="c1",
        selected_role="Backend Developer",
        inferred_level="mid",
        strong_skills=[],
        weak_skills=[],
        skill_mastery={"API Design": 60, "Database": 55, "Concurrency": 50},
        confidence_trend="stable",
        communication_trend="fair",
        risk_flags=[],
        last_decision="post_answer_update",
        next_best_action="API Design",
    )
    defaults.update(kwargs)
    return CandidateState(**defaults)


def _make_plan(topics=None):
    topics = topics or ["API Design", "Database", "Concurrency"]
    return [
        InterviewPlanItem(
            step=i + 1, topic=t, difficulty="medium",
            reason="Core topic", linked_resume_evidence=[], target_skill=t,
        )
        for i, t in enumerate(topics)
    ]


class TestIntelligenceEngineSignalOverride:
    def test_strong_technical_low_confidence_pivot(self):
        """
        When signal = strong_technical_low_confidence and base decision would be
        deeper_follow_up, it should pivot to confidence_recovery so the candidate
        gets encouraging framing without reducing difficulty.
        """
        state = _make_state()
        # tech=75 (strong) → base would be "deeper_follow_up"
        trace = make_next_question_decision(
            candidate_state=state,
            last_evaluation={"technical_score": 75, "depth_score": 65,
                             "covered_points": ["REST basics"], "missing_points": []},
            current_question={"topic": "API Design", "difficulty": "medium"},
            interview_plan=_make_plan(),
            session_history=[],
            audio_score={"confidence_score": 40, "communication_clarity_score": 75},
            video_score={"engagement_score": 70},
            multimodal_score={
                "combined_score": 70,
                "multimodal_signal": "strong_technical_low_confidence",
            },
        )
        assert trace.decision_type == "confidence_recovery"

    def test_strong_candidate_escalates(self):
        """
        strong_candidate signal should push toward increase_difficulty.
        """
        state = _make_state()
        trace = make_next_question_decision(
            candidate_state=state,
            last_evaluation={"technical_score": 82, "depth_score": 70,
                             "covered_points": ["indexing"], "missing_points": []},
            current_question={"topic": "Database", "difficulty": "medium"},
            interview_plan=_make_plan(),
            session_history=[{"question": {"topic": "API Design"}}],
            multimodal_score={
                "combined_score": 78,
                "multimodal_signal": "strong_candidate",
            },
        )
        assert trace.decision_type == "increase_difficulty"

    def test_weak_technical_low_confidence_remediates(self):
        state = _make_state()
        trace = make_next_question_decision(
            candidate_state=state,
            last_evaluation={"technical_score": 35, "depth_score": 30,
                             "covered_points": [], "missing_points": ["concurrency basics"]},
            current_question={"topic": "Concurrency", "difficulty": "medium"},
            interview_plan=_make_plan(),
            session_history=[],
            multimodal_score={
                "combined_score": 35,
                "multimodal_signal": "weak_technical_low_confidence",
            },
        )
        assert trace.decision_type in ("strengthen_fundamentals", "remediation")

    def test_multimodal_signal_in_evidence(self):
        state = _make_state()
        trace = make_next_question_decision(
            candidate_state=state,
            last_evaluation={"technical_score": 80, "depth_score": 65,
                             "covered_points": [], "missing_points": []},
            current_question={"topic": "API Design", "difficulty": "medium"},
            interview_plan=_make_plan(),
            session_history=[],
            multimodal_score={
                "combined_score": 75,
                "multimodal_signal": "strong_technical",
            },
        )
        evidence_text = " ".join(trace.evidence)
        assert "strong technical" in evidence_text

    def test_no_multimodal_score_uses_defaults(self):
        """Passing multimodal_score=None must not raise an exception."""
        state = _make_state()
        trace = make_next_question_decision(
            candidate_state=state,
            last_evaluation={"technical_score": 60, "depth_score": 55,
                             "covered_points": [], "missing_points": []},
            current_question={"topic": "API Design", "difficulty": "medium"},
            interview_plan=_make_plan(),
            session_history=[],
            multimodal_score=None,
        )
        assert trace.decision_type in (
            "increase_difficulty", "deeper_follow_up", "strengthen_fundamentals",
            "confidence_recovery", "remediation", "final_synthesis",
        )


# ── 6. Encouragement vs penalty (scoring philosophy) ─────────────────────────

class TestScoringPhilosophy:
    def test_nervousness_does_not_heavily_penalise_strong_tech(self):
        """
        A nervousness signal alone should NOT reduce the combined_score so much
        that a technically strong candidate ends up below 60.
        """
        evaluation = {"technical_score": 85, "depth_score": 75}
        audio = {
            "communication_clarity_score": 55,
            "confidence_score": 40,           # very nervous
            "pause_count": 4,
            "hesitation_count": 4,
        }
        video = {"engagement_score": 70, "movement_activity": "high"}
        result = aggregate_turn(evaluation, audio, video, role_fit_score=75,
                                role="Backend Developer")
        # Technical dominates for Backend Developer (weight 0.55)
        assert result["combined_score"] >= 60

    def test_communication_rewards_structure_not_verbosity(self):
        """
        Two answers: one short + well-paced (good structure proxy),
        one very long but with high filler ratio (verbosity).
        Clarity score should be similar or favour the structured answer.
        """
        from services.audio_analyzer import _score_clarity
        # Structured answer: medium pace, 80 words, low fillers, low hesitation
        score_structured = _score_clarity("medium", 80, 0.02, "low")
        # Verbose answer: medium pace, 300 words, high fillers, high hesitation
        score_verbose    = _score_clarity("medium", 300, 0.12, "high")
        assert score_structured >= score_verbose


# ── 7. Fallback path exposes new fields ───────────────────────────────────────

class TestFallbackNewFields:
    def test_audio_fallback_has_new_orchestrator_fields(self):
        import asyncio
        import os
        # Patch engine to fallback
        import services.audio_analyzer as aa
        orig_engine = aa._ENGINE
        aa._ENGINE = "fallback"
        try:
            result = asyncio.run(aa.analyze(b"x" * 20000, "test.webm"))
        finally:
            aa._ENGINE = orig_engine
        assert "pace_label" in result
        assert "detected_issue" in result
        assert "recommendation_to_orchestrator" in result
        assert "coaching_tip" in result
        assert "audio_reasoning_summary" in result

    def test_video_fallback_has_new_orchestrator_fields(self):
        from services.video_analyzer import _analyze_fallback
        result = _analyze_fallback(b"x" * 500000, False)
        assert "nervousness_proxy_score" in result
        assert "looking_away_proxy_score" in result
        assert "visual_reasoning_summary" in result
        assert "recommendation_to_orchestrator" in result
        assert result["metrics_source"] == "heuristic"


# ── 8. Session aggregation includes multimodal_signal ─────────────────────────

class TestSessionAggregation:
    def test_aggregate_session_returns_dominant_signal(self):
        answers = [
            {"evaluation": {"technical_score": 80, "depth_score": 70}},
            {"evaluation": {"technical_score": 75, "depth_score": 65}},
        ]
        result = multimodal_aggregator.aggregate_session(
            answers, [], [], 75, role="Backend Developer"
        )
        assert "multimodal_signal" in result
        assert isinstance(result["multimodal_signal"], str)
        assert result["weights"]["technical"] == 0.55

    def test_aggregate_session_role_weights_propagate(self):
        answers = [{"evaluation": {"technical_score": 80, "depth_score": 70}}]
        result = multimodal_aggregator.aggregate_session(
            answers, [], [], 75, role="Product Manager"
        )
        assert result["weights"]["technical"] == 0.20
        assert result["weights"]["communication"] == 0.35
