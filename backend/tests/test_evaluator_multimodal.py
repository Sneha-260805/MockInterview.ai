import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agents import evaluator_agent
from models.interview import EvaluateAnswerRequest
from services import multimodal_aggregator


@pytest.mark.asyncio
async def test_empty_answer_scores_zero(monkeypatch):
    from config import get_settings
    monkeypatch.setenv("USE_LLM", "false")
    get_settings.cache_clear()
    req = EvaluateAnswerRequest(
        session_id="s",
        question_id="q",
        question="Explain REST",
        answer="",
        expected_points=["statelessness", "HTTP verbs"],
    )
    result = await evaluator_agent.evaluate(req)
    assert result.technical_score == 0
    assert result.depth_score == 0
    assert result.correctness_score == 0


@pytest.mark.asyncio
async def test_irrelevant_short_answer_scores_low(monkeypatch):
    from config import get_settings
    monkeypatch.setenv("USE_LLM", "false")
    get_settings.cache_clear()
    req = EvaluateAnswerRequest(
        session_id="s",
        question_id="q",
        question="Explain REST",
        answer="I like pizza",
        expected_points=["statelessness", "HTTP verbs"],
    )
    result = await evaluator_agent.evaluate(req)
    assert result.technical_score <= 8
    assert result.correctness_score <= 8


def test_multimodal_aggregation_uses_weights_and_evidence():
    result = multimodal_aggregator.aggregate_turn(
        {"technical_score": 80, "depth_score": 70},
        {"communication_clarity_score": 75, "confidence_score": 70, "pause_count": 1, "hesitation_count": 1},
        {"engagement_score": 65, "posture_score": 70, "stress_indicator": "medium"},
        role_fit_score=90,
    )
    assert result["weights"]["technical"] == 0.45
    assert 0 <= result["combined_score"] <= 100
    assert result["source"] == "multimodal"
    assert result["evidence"]
