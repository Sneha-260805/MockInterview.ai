"""Tests for agent decision context in question generation."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from models.agent_state import AgentDecisionTrace
from services import question_generator
from services.question_generator import build_llm_prompt


def _sample_trace(decision_type: str = "deeper_follow_up") -> AgentDecisionTrace:
    return AgentDecisionTrace(
        decision_type=decision_type,
        previous_topic="API Design",
        previous_score=65,
        detected_issue="Good performance with minor gaps on API Design.",
        next_topic="Database",
        next_difficulty="medium",
        reason_for_adaptation="Probing remaining depth on API Design.",
        evidence=["Technical score on Q: 65/100", "Missing: idempotency keys"],
    )


def test_build_llm_prompt_includes_decision_type_and_missing_concepts():
    ctx = question_generator._build_decision_context(
        decision_type="deeper_follow_up",
        decision_reason="Probe gaps from the last answer.",
        missing_concepts=["idempotency keys", "retry strategy"],
        covered_concepts=["REST basics"],
        current_topic="API Design",
        previous_question="Explain idempotency in REST APIs.",
        previous_answer="Idempotency means the same result when called twice.",
        confidence_score=72,
        communication_score=68,
        engagement_score=80,
        stay_on_topic=True,
    )
    prompt = build_llm_prompt(
        "Backend Developer",
        "Database",
        "medium",
        None,
        ctx,
    )
    assert "deeper_follow_up" in prompt
    assert "idempotency keys" in prompt
    assert "Probe gaps from the last answer." in prompt
    assert "stay_on_topic: True" in prompt
    assert "Confidence score: 72/100" in prompt


@pytest.mark.asyncio
async def test_generate_question_passes_decision_context_to_llm(monkeypatch):
    from config import get_settings

    captured: dict = {}

    async def _mock_call_llm(prompt, max_tokens=700):
        captured["prompt"] = prompt
        return json.dumps(
            {
                "question": "You mentioned idempotency — how would you implement idempotency keys for a payment API?",
                "topic": "API Design",
                "difficulty": "medium",
                "question_type": "follow_up",
                "expected_concepts": ["idempotency keys", "deduplication"],
                "expected_points": ["idempotency keys", "deduplication"],
                "why_selected": "Follow-up to close gaps on idempotency.",
                "followup_of_previous": True,
                "follow_up_intent": "Probe implementation depth.",
                "target_skill": "API Design",
            }
        )

    class _Settings:
        has_llm_configured = True
        llm_provider = "gemini"

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_call_llm)

    trace = _sample_trace()
    q = await question_generator.generate_question(
        "Backend Developer",
        "Database",
        "medium",
        previous_answer="Idempotency means same result on repeat calls.",
        previous_missing=["idempotency keys"],
        decision_type=trace.decision_type,
        decision_reason=trace.reason_for_adaptation,
        decision_trace=trace,
        missing_concepts=["idempotency keys"],
        covered_concepts=["REST basics"],
        current_topic="API Design",
        previous_question="Explain idempotency in REST APIs.",
        confidence_score=70,
        communication_score=75,
        engagement_score=65,
        stay_on_topic=True,
    )

    assert "deeper_follow_up" in captured["prompt"]
    assert "idempotency keys" in captured["prompt"]
    assert q.generation_mode == "llm"
    assert q.why_selected == "Follow-up to close gaps on idempotency."
    assert q.followup_of_previous is True
    assert q.question_type == "follow_up"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_fallback_respects_remediation_decision_type(monkeypatch):
    from config import get_settings

    monkeypatch.setenv("USE_LLM", "false")
    get_settings.cache_clear()

    q = await question_generator.generate_question(
        "Backend Developer",
        "API Design",
        "medium",
        previous_answer="I use POST for everything.",
        previous_missing=["HTTP method semantics"],
        decision_type="strengthen_fundamentals",
        decision_reason="Return to foundational HTTP concepts.",
        missing_concepts=["HTTP method semantics"],
        current_topic="API Design",
        stay_on_topic=False,
    )

    assert q.generation_mode == "deterministic_dynamic"
    assert q.question_type == "fundamentals"
    assert "HTTP method semantics" in q.question
    assert q.why_selected == "Return to foundational HTTP concepts."

    get_settings.cache_clear()


# ── Step 6: Behavioral probe question generation ───────────────────────────────

@pytest.mark.asyncio
async def test_behavioral_question_generation_uses_decision_context(monkeypatch):
    """
    When decision_type='behavioral_probe', question_generator must return:
    - question_type == "behavioral"
    - topic == "Behavioral & Communication"
    - why_selected references behavioral validation, role, or communication
    This runs via the deterministic fallback (no LLM) so it is always reproducible.
    """
    from config import get_settings

    monkeypatch.setenv("USE_LLM", "false")
    get_settings.cache_clear()

    q = await question_generator.generate_question(
        "Backend Developer",
        "Behavioral & Communication",
        "medium",
        decision_type="behavioral_probe",
        decision_reason="Candidate has answered 2 technical questions. Now assessing soft skills.",
        current_topic="API Design",
    )

    assert q.question_type == "behavioral", (
        f"Expected question_type='behavioral', got '{q.question_type}'"
    )
    assert q.topic == "Behavioral & Communication", (
        f"Expected topic='Behavioral & Communication', got '{q.topic}'"
    )
    why = (q.why_selected or "").lower()
    assert any(w in why for w in ("behavioral", "soft", "communication", "ownership", "assessment")), (
        f"why_selected should reference behavioral validation, got: {q.why_selected!r}"
    )
    assert q.question.strip(), "Question text must be non-empty"
    assert len(q.expected_points) >= 3, "Behavioral question should have evaluation criteria"

    get_settings.cache_clear()


def test_fallback_orchestrator_behavioral_unchanged():
    """
    The orchestrator's fallback behavioral bank and Q3 rule must remain intact.
    Primary-path behavioral_probe does NOT replace orchestrator logic — it
    supplements it so the fallback is still available if the primary path fails.
    """
    from agents.interview_orchestrator import _BEHAVIORAL_BANK

    assert isinstance(_BEHAVIORAL_BANK, list), "_BEHAVIORAL_BANK must be a list"
    assert len(_BEHAVIORAL_BANK) >= 4, (
        f"Behavioral bank should have at least 4 questions, has {len(_BEHAVIORAL_BANK)}"
    )
    for entry in _BEHAVIORAL_BANK:
        assert entry.get("q"), "Each bank entry must have a question text"
        assert entry.get("t") == "Behavioral & Communication", (
            f"Bank entry topic should be 'Behavioral & Communication', got {entry.get('t')!r}"
        )
        assert entry.get("d") in ("easy", "medium", "hard"), (
            f"Bank entry difficulty invalid: {entry.get('d')!r}"
        )
