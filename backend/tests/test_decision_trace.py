"""Tests for judge-ready AgentDecisionTrace enrichment (Step 4)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agents.intelligence_engine import make_next_question_decision
from models.agent_state import AgentDecisionTrace, CandidateState, InterviewPlanItem
from models.interview import Question
from services import followup_primary
from services.trace_enrichment import enrich_trace_after_question


def _plan():
    return [
        InterviewPlanItem(step=1, topic="API Design", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
        InterviewPlanItem(step=2, topic="Database Indexing", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
    ]


def _weak_state():
    return CandidateState(
        session_id="s1",
        candidate_id="c1",
        selected_role="Backend Developer",
        inferred_level="mid",
        strong_skills=[],
        weak_skills=["Database Indexing"],
        skill_mastery={"Database Indexing": 32, "API Design": 55},
        confidence_trend="declining",
        communication_trend="fair",
        risk_flags=["Repeated weakness on 'Database Indexing' — needs remediation"],
        last_decision="",
        next_best_action="Database Indexing",
        concept_gaps={"query plan": 2, "index selectivity": 3},
    )


class TestWeakAnswerTrace:
    def test_weak_answer_trace_has_observation_and_rationales(self):
        trace = make_next_question_decision(
            _weak_state(),
            {
                "technical_score": 38,
                "depth_score": 30,
                "missing_points": ["query plan", "index selectivity"],
                "covered_points": [],
            },
            {"topic": "Database Indexing", "difficulty": "medium"},
            _plan(),
            [{"question": {"topic": "Database Indexing"}}],
        )
        obs = trace.observation.lower()
        assert any(w in obs for w in ("shallow", "weak", "missed", "query plan"))
        assert trace.signal_scores.get("technical") == 38
        assert trace.signal_scores.get("depth") == 30
        assert trace.topic_rationale
        assert trace.difficulty_rationale
        assert trace.next_question_strategy


class TestStrongAnswerTrace:
    def test_strong_answer_trace(self):
        state = CandidateState(
            session_id="s1",
            candidate_id="c1",
            selected_role="Backend Developer",
            inferred_level="mid",
            strong_skills=[],
            weak_skills=[],
            skill_mastery={"API Design": 70},
            confidence_trend="improving",
            communication_trend="good",
            risk_flags=[],
            last_decision="",
            next_best_action="",
        )
        trace = make_next_question_decision(
            state,
            {"technical_score": 88, "depth_score": 82, "missing_points": [], "covered_points": ["REST"]},
            {"topic": "API Design", "difficulty": "medium"},
            _plan(),
            [],
            audio_score={"confidence_score": 85, "communication_clarity_score": 80, "mode": "whisper"},
        )
        assert "strong" in trace.observation.lower()
        assert trace.decision_type == "increase_difficulty"
        assert trace.difficulty_rationale
        assert any(w in trace.difficulty_rationale.lower() for w in ("increase", "increased", "hard"))


class TestUnavailableSignals:
    def test_unavailable_confidence_not_shown_as_real_100(self):
        state = CandidateState(
            session_id="s1",
            candidate_id="c1",
            selected_role="Backend Developer",
            inferred_level="mid",
            strong_skills=[],
            weak_skills=[],
            skill_mastery={"API Design": 60},
            confidence_trend="unknown",
            communication_trend="unknown",
            risk_flags=[],
            last_decision="",
            next_best_action="",
        )
        trace = make_next_question_decision(
            state,
            {"technical_score": 65, "depth_score": 60, "missing_points": [], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            _plan(),
            [],
        )
        assert trace.confidence_available is False
        assert trace.communication_available is False
        assert trace.engagement_available is False
        assert trace.signal_scores.get("confidence") is None
        assert trace.signal_scores.get("communication") is None
        assert trace.signal_scores.get("engagement") is None
        assert "available" in trace.confidence_note.lower()


@pytest.mark.asyncio
async def test_followup_generation_trace(monkeypatch):
    trace = AgentDecisionTrace(
        decision_type="deeper_follow_up",
        previous_topic="Performance Optimization",
        previous_score=65,
        detected_issue="Partial understanding.",
        next_topic="Performance Optimization",
        next_difficulty="medium",
        reason_for_adaptation="Stay on topic.",
        evidence=["Missing: cache invalidation"],
        observation="Candidate showed partial understanding on 'Performance Optimization'.",
        next_question_strategy="same_topic_depth_probe",
    )
    answer = "I used Redis to improve API performance."

    q, evidence = followup_primary.try_build_followup_question(
        trace,
        answer=answer,
        current_topic="Performance Optimization",
        resume_techs=["Redis"],
        missing_concepts=["cache invalidation"],
        covered_concepts=[],
        previous_question="How did you optimize performance?",
        difficulty="medium",
    )
    assert q is not None
    enriched = enrich_trace_after_question(
        followup_primary.enrich_trace_with_followup(trace, evidence or ""),
        q,
        generation_mode="followup_generator",
        generated_question_reason=q.why_selected or "",
        answer_text=answer,
    )
    assert enriched.generation_mode == "followup_generator"
    assert enriched.generated_question_reason
    assert enriched.followup_of_previous is True
    assert "redis" in enriched.observation.lower() or "cache" in enriched.observation.lower()
    assert any("followup_generator" in e for e in enriched.evidence)


@pytest.mark.asyncio
async def test_question_generator_trace(monkeypatch):
    from config import get_settings

    monkeypatch.setenv("USE_LLM", "false")
    get_settings.cache_clear()

    trace = AgentDecisionTrace(
        decision_type="deeper_follow_up",
        previous_topic="API Design",
        previous_score=65,
        detected_issue="Gaps remain.",
        next_topic="API Design",
        next_difficulty="medium",
        reason_for_adaptation="Probe depth.",
        evidence=[],
        observation="Partial answer.",
        next_question_strategy="same_topic_depth_probe",
    )

    def _noop_followup(*args, **kwargs):
        return None, None

    monkeypatch.setattr(followup_primary, "try_build_followup_question", _noop_followup)

    q, enriched = await followup_primary.resolve_primary_next_question(
        trace,
        role="Backend Developer",
        analysis=None,
        last_answer_text="It was fine.",
        last_eval={"missing_points": [], "covered_points": []},
        current_q_dict={"topic": "API Design", "question": "Explain REST."},
        body_current_topic="API Design",
        turn_multi={},
        resume_techs=[],
    )

    assert enriched.generation_mode == "question_generator"
    assert enriched.generated_question_reason
    assert any("question_generator" in e for e in enriched.evidence)
    assert q.question

    get_settings.cache_clear()
