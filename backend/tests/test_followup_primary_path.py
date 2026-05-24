"""Tests for primary-path follow-up wiring (Step 3)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from models.agent_state import AgentDecisionTrace
from models.interview import Question
from services import followup_generator, followup_primary


def _trace(decision_type: str = "deeper_follow_up", **kwargs) -> AgentDecisionTrace:
    defaults = dict(
        decision_type=decision_type,
        previous_topic="Performance Optimization",
        previous_score=65,
        detected_issue="Partial understanding with implementation gaps.",
        next_topic="Performance Optimization",
        next_difficulty="medium",
        reason_for_adaptation="Staying on topic to probe depth.",
        evidence=["Technical score on Q: 65/100"],
        next_question_strategy="same_topic_depth_probe",
    )
    defaults.update(kwargs)
    return AgentDecisionTrace(**defaults)


def test_primary_path_uses_followup_for_redis_claim():
    trace = _trace("deeper_follow_up", next_topic="Performance Optimization")
    answer = "I used Redis to improve API performance."

    q, evidence = followup_primary.try_build_followup_question(
        trace,
        answer=answer,
        current_topic="Performance Optimization",
        resume_techs=["Redis", "Python"],
        missing_concepts=["cache invalidation"],
        covered_concepts=["caching"],
        previous_question="How did you optimize API performance?",
        difficulty="medium",
    )

    assert q is not None
    assert q.generation_mode == "followup_generator"
    assert q.followup_of_previous is True
    assert "redis" in q.question.lower() or "cache" in q.question.lower()
    combined = " ".join(q.expected_points).lower()
    assert any(term in combined for term in ("invalidation", "ttl", "stale", "cache"))
    assert evidence and "follow-up" in evidence.lower()


def test_primary_path_uses_followup_for_authentication_claim():
    trace = _trace("verify_resume_claim", next_topic="Authentication")
    answer = "I worked on authentication for the platform."

    q, evidence = followup_primary.try_build_followup_question(
        trace,
        answer=answer,
        current_topic="Authentication",
        resume_techs=["JWT", "OAuth"],
        missing_concepts=["route protection"],
        covered_concepts=[],
        previous_question="Tell me about your auth work.",
        difficulty="medium",
    )

    assert q is not None
    assert q.question_type == "claim_verification"
    assert any(
        term in q.question.lower()
        for term in ("authentication", "protect", "unauthorized", "route")
    )
    concepts = " ".join(q.expected_points).lower()
    assert any(term in concepts for term in ("jwt", "oauth", "authorization", "route"))


@pytest.mark.asyncio
async def test_primary_path_falls_back_to_question_generator_when_no_followup(monkeypatch):
    from config import get_settings

    monkeypatch.setenv("USE_LLM", "false")
    get_settings.cache_clear()

    trace = _trace("deeper_follow_up")
    called = {"generate_question": False}

    async def _fake_generate_question(*args, **kwargs):
        called["generate_question"] = True
        return Question(
            question_id="QTEST0001",
            question="Fallback generated question about API design.",
            difficulty="medium",
            topic="API Design",
            expected_points=["validation"],
            generation_mode="deterministic_dynamic",
        )

    monkeypatch.setattr(followup_primary.question_generator, "generate_question", _fake_generate_question)

    q, returned_trace = await followup_primary.resolve_primary_next_question(
        trace,
        role="Backend Developer",
        analysis=None,
        last_answer_text="It was fine.",
        last_eval={"missing_points": [], "covered_points": []},
        current_q_dict={"topic": "API Design", "question": "Explain REST."},
        body_current_topic="API Design",
        turn_multi={"confidence_score": 70, "communication_score": 70, "engagement_score": 70},
        resume_techs=[],
    )

    assert called["generate_question"] is True
    assert q.generation_mode == "deterministic_dynamic"
    assert returned_trace.decision_type == "deeper_follow_up"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_followup_generator_failure_does_not_break_next_question(monkeypatch):
    from config import get_settings

    monkeypatch.setenv("USE_LLM", "false")
    get_settings.cache_clear()

    trace = _trace("deeper_follow_up")

    def _boom(*args, **kwargs):
        raise RuntimeError("followup generator exploded")

    async def _fake_generate_question(*args, **kwargs):
        return Question(
            question_id="QTEST0002",
            question="Safe fallback question.",
            difficulty="easy",
            topic="API Design",
            expected_points=["basics"],
            generation_mode="deterministic_dynamic",
        )

    monkeypatch.setattr(followup_primary, "should_try_followup", lambda *a, **k: True)
    monkeypatch.setattr(followup_primary.followup_generator, "generate_followup", _boom)
    monkeypatch.setattr(followup_primary.question_generator, "generate_question", _fake_generate_question)

    q, _ = await followup_primary.resolve_primary_next_question(
        trace,
        role="Backend Developer",
        analysis=None,
        last_answer_text="I used Redis for caching.",
        last_eval={"missing_points": ["TTL"], "covered_points": []},
        current_q_dict={"topic": "Performance", "question": "Caching?"},
        body_current_topic="Performance",
        turn_multi={"confidence_score": 60},
        resume_techs=["Redis"],
    )

    assert q.question == "Safe fallback question."

    get_settings.cache_clear()


def test_orchestrator_fallback_followup_unchanged():
    """Orchestrator still imports and calls generate_followup in its own path."""
    import inspect
    from agents import interview_orchestrator

    source = inspect.getsource(interview_orchestrator.next_question)
    assert "generate_followup" in source
    assert "Behavioral & Communication" in source


def test_followup_trace_mentions_reason():
    trace = _trace("deeper_follow_up")
    answer = "I used Redis to improve API performance."

    q, evidence = followup_primary.try_build_followup_question(
        trace,
        answer=answer,
        current_topic="Performance Optimization",
        resume_techs=["Redis"],
        missing_concepts=["cache invalidation", "TTL"],
        covered_concepts=[],
        previous_question="Performance?",
        difficulty="medium",
    )
    enriched = followup_primary.enrich_trace_with_followup(trace, evidence or "")

    assert q is not None
    assert any("follow-up generated" in e.lower() for e in enriched.evidence)
    assert any("redis" in e.lower() or "candidate answer" in e.lower() for e in enriched.evidence)


def test_followup_generator_redis_question_text():
    result = followup_generator.generate_followup(
        "I used Redis to improve API performance.",
        current_topic="Performance Optimization",
        decision_type="deeper_follow_up",
    )
    assert result is not None
    question, reason, points = result
    assert "invalidation" in question.lower() or "ttl" in " ".join(points).lower()
    assert "redis" in reason.lower()


def test_followup_generator_backend_api_claim():
    result = followup_generator.generate_followup(
        "I built the backend APIs for our service.",
        current_topic="API Design",
        decision_type="deeper_follow_up",
    )
    assert result is not None
    question, _, points = result
    assert "api" in question.lower()
    concepts = " ".join(points).lower()
    assert "validation" in concepts or "error handling" in concepts
