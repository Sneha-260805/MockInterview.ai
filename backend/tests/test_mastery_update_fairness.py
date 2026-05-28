"""
Phase 4 — Mastery Update Fairness tests

Verifies that update_candidate_state() applies question-type-aware observation
weights, skips technical mastery for behavioral answers, records last_mastery_update,
preserves improve-answer semantics, and improves next_best_action logic.

Baseline: 259 passed, 2 skipped (pre-Phase-4).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.agent_state import CandidateState
from agents.intelligence_engine import (
    update_candidate_state,
    update_candidate_state_for_improvement,
    _OBS_WEIGHT_BY_QTYPE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_state(skill_mastery: dict, answers_answered: int = 0) -> CandidateState:
    return CandidateState(
        session_id="test-session",
        candidate_id="test-cand",
        selected_role="Backend Developer",
        inferred_level="mid",
        strong_skills=["Python", "REST APIs"],
        weak_skills=[],
        skill_mastery=skill_mastery,
        confidence_trend="unknown",
        communication_trend="unknown",
        risk_flags=[],
        last_decision="session_start",
        next_best_action=next(iter(skill_mastery), ""),
        answers_answered=answers_answered,
    )


def _make_answer_record(topic: str, tech_score: int, covered: list = None, missing: list = None):
    return {
        "question_id": "q-test",
        "question": f"Explain {topic}",
        "answer_text": "A detailed answer covering multiple points about the topic.",
        "topic": topic,
        "evaluation": {
            "technical_score": tech_score,
            "depth_score": 70,
            "correctness_score": 75,
            "covered_points": covered or ["concept A", "concept B"],
            "missing_points": missing or [],
        },
    }


# ── Test 1: strong technical_concept answer raises topic mastery ──────────────

def test_strong_concept_answer_raises_topic_mastery():
    """
    A high-scoring technical_concept answer (tech=90) should raise a topic
    that started at 55.  obs_weight for technical_concept is 0.55, so
    updated = round(55 * 0.45 + 90 * 0.55) = round(24.75 + 49.5) = 74.
    """
    state = _make_state({"Vector Search": 55})
    record = _make_answer_record("Vector Search", tech_score=90)

    updated = update_candidate_state(
        state, record, question_type="technical_concept"
    )

    assert updated.skill_mastery["Vector Search"] > 55, (
        f"Expected mastery > 55 after strong concept answer, "
        f"got {updated.skill_mastery['Vector Search']}"
    )
    assert updated.skill_mastery["Vector Search"] == 74


# ── Test 2: concept answer without project mention still raises mastery ────────

def test_concept_answer_without_project_mention_raises_mastery():
    """
    A technical_concept answer that never mentions a specific project should
    still raise mastery.  Phase 4 obs_weight is 0.45 regardless of project
    language (rubric scoring is separate from mastery update).
    """
    state = _make_state({"RAG Pipeline Design": 50})
    record = _make_answer_record("RAG Pipeline Design", tech_score=80)
    record["answer_text"] = (
        "RAG retrieves relevant chunks from a vector store and passes them "
        "as context to the LLM, improving factual grounding without retraining."
    )

    updated = update_candidate_state(
        state, record, question_type="technical_concept"
    )

    assert updated.skill_mastery["RAG Pipeline Design"] > 50


# ── Test 3: technical_follow_up raises related topic mastery ─────────────────

def test_technical_followup_raises_related_topic_mastery():
    """
    A technical_follow_up answer uses obs_weight 0.50.
    Starting at 60: round(60 * 0.50 + 85 * 0.50) = round(30 + 42.5) = 72.
    """
    state = _make_state({"Authentication": 60})
    record = _make_answer_record("Authentication", tech_score=85)

    updated = update_candidate_state(
        state, record, question_type="technical_follow_up"
    )

    expected = round(60 * 0.50 + 85 * 0.50)   # 72
    assert updated.skill_mastery["Authentication"] == expected, (
        f"Expected {expected}, got {updated.skill_mastery['Authentication']}"
    )


# ── Test 4: behavioral answer does NOT reduce technical mastery ───────────────

def test_behavioral_answer_does_not_reduce_technical_mastery():
    """
    A low-scoring behavioral answer (tech=20) must NOT reduce the candidate's
    technical mastery for any topic.  obs_weight for behavioral is 0.00.
    """
    state = _make_state({"System Design": 75, "Authentication": 80})
    record = _make_answer_record("System Design", tech_score=20)
    record["answer_text"] = "I worked with a team on a big project once."

    updated = update_candidate_state(
        state, record, question_type="behavioral"
    )

    assert updated.skill_mastery["System Design"] == 75, (
        f"Behavioral answer should not change mastery; got {updated.skill_mastery['System Design']}"
    )
    assert updated.skill_mastery["Authentication"] == 80


# ── Test 5: behavioral answer skips adjacent topic propagation ────────────────

def test_behavioral_answer_skips_adjacent_topic_propagation():
    """
    update_candidate_state with question_type=behavioral must not propagate
    any signal to adjacent topics (e.g. REST Fundamentals → API Design).
    """
    state = _make_state({"REST Fundamentals": 70, "API Design": 65, "Authentication": 60})
    record = _make_answer_record("REST Fundamentals", tech_score=10)

    updated = update_candidate_state(
        state, record, question_type="behavioral"
    )

    # Adjacent topics should be unchanged
    assert updated.skill_mastery["API Design"] == 65
    assert updated.skill_mastery["Authentication"] == 60


# ── Test 6: project_deep_dive updates project topic, not unrelated topics ─────

def test_project_deep_dive_updates_project_topic_not_unrelated_topics():
    """
    A project_deep_dive answer should update the answered topic (obs_weight=0.40)
    but must NOT touch unrelated topics that are not in _ADJACENT_TOPICS.
    """
    state = _make_state(
        {"Database Design": 50, "RAG Pipeline Design": 60, "Attention Mechanisms": 70}
    )
    record = _make_answer_record("Database Design", tech_score=85)

    updated = update_candidate_state(
        state, record, question_type="project_deep_dive"
    )

    # Database Design should be updated (obs_weight=0.40)
    expected_db = round(50 * 0.60 + 85 * 0.40)   # round(30 + 34) = 64
    assert updated.skill_mastery["Database Design"] == expected_db, (
        f"Expected {expected_db}, got {updated.skill_mastery['Database Design']}"
    )
    # Unrelated topic must be untouched
    assert updated.skill_mastery["Attention Mechanisms"] == 70


# ── Test 7: claim_verification updates related topic with moderate weight ──────

def test_claim_verification_updates_related_topic_moderately():
    """
    claim_verification obs_weight is 0.35 — lighter than technical_concept (0.55).
    A strong answer on "Authentication" starting at 55:
    round(55 * 0.65 + 88 * 0.35) = round(35.75 + 30.8) = 67.
    """
    state = _make_state({"Authentication": 55})
    record = _make_answer_record("Authentication", tech_score=88)

    updated = update_candidate_state(
        state, record, question_type="claim_verification"
    )

    expected = round(55 * 0.65 + 88 * 0.35)   # 67
    assert updated.skill_mastery["Authentication"] == expected, (
        f"Expected {expected}, got {updated.skill_mastery['Authentication']}"
    )


# ── Test 8: improve-answer does not double-count answers_answered ─────────────

def test_improve_answer_mastery_update_does_not_double_count():
    """
    update_candidate_state_for_improvement() must NOT increment answers_answered.
    The original answer already incremented it; the improved answer is a retry of
    the same question.
    """
    state = _make_state({"System Design": 50}, answers_answered=2)
    record = _make_answer_record("System Design", tech_score=75)
    prev_eval = {"technical_score": 45, "covered_points": [], "missing_points": ["concept A"]}

    updated = update_candidate_state_for_improvement(
        state, record, previous_evaluation=prev_eval
    )

    assert updated.answers_answered == 2, (
        f"answers_answered must stay at 2 after improve-answer, got {updated.answers_answered}"
    )


# ── Test 9: next_best_action prefers weak concept after project_deep_dive ──────

def test_next_best_action_prefers_weak_concept_when_project_quota_exhausted():
    """
    After a project_deep_dive on topic A, next_best_action should be the weakest
    OTHER topic (not A itself), because repeatedly drilling the same project area
    wastes interview time once the quota for project questions is used.

    Setup: "Database Design" (just answered, mastery 40 → updated),
           "Vector Search" (mastery 35 — weaker),
           "RAG Pipeline Design" (mastery 50).

    After project_deep_dive on "Database Design", next_best_action should be
    "Vector Search" (weakest non-answered topic), not "Database Design".
    """
    state = _make_state(
        {"Database Design": 40, "Vector Search": 35, "RAG Pipeline Design": 50}
    )
    record = _make_answer_record("Database Design", tech_score=70)

    updated = update_candidate_state(
        state, record, question_type="project_deep_dive"
    )

    assert updated.next_best_action != "Database Design", (
        "next_best_action must not loop back to the just-probed project topic; "
        f"got '{updated.next_best_action}'"
    )
    assert updated.next_best_action == "Vector Search", (
        f"Expected 'Vector Search' (weakest non-project topic), "
        f"got '{updated.next_best_action}'"
    )


# ── Test 10: last_mastery_update is populated correctly ───────────────────────

def test_last_mastery_update_populated():
    """
    After a non-behavioral update, state.last_mastery_update must be a dict
    with topic, question_type, previous_mastery, new_mastery, score_used,
    covered_concepts, and missing_concepts keys.
    """
    state = _make_state({"API Design": 60})
    record = _make_answer_record(
        "API Design", tech_score=80,
        covered=["REST methods", "status codes"], missing=["rate limiting"]
    )

    updated = update_candidate_state(
        state, record, question_type="technical_concept"
    )

    lmu = updated.last_mastery_update
    assert lmu is not None
    assert lmu["topic"] == "API Design"
    assert lmu["question_type"] == "technical_concept"
    assert lmu["previous_mastery"] == 60
    assert lmu["score_used"] == 80
    assert "REST methods" in lmu["covered_concepts"]
    assert "rate limiting" in lmu["missing_concepts"]


# ── Test 11: behavioral last_mastery_update records skip reason ───────────────

def test_behavioral_last_mastery_update_records_skip():
    """
    After a behavioral answer, last_mastery_update must record the skip with
    a 'behavioral answer — technical mastery not updated' reason.
    """
    state = _make_state({"System Design": 70})
    record = _make_answer_record("System Design", tech_score=30)

    updated = update_candidate_state(
        state, record, question_type="behavioral"
    )

    lmu = updated.last_mastery_update
    assert lmu is not None
    assert "behavioral" in lmu["reason"].lower()
    assert lmu["previous_mastery"] == lmu["new_mastery"]


# ── Test 12: obs_weight constant sanity ──────────────────────────────────────

def test_obs_weight_by_qtype_values():
    """
    _OBS_WEIGHT_BY_QTYPE must define 0.00 for behavioral types and positive
    weights for all concept/project types.  All weights must be in [0.0, 1.0].
    """
    assert _OBS_WEIGHT_BY_QTYPE["behavioral"] == 0.00
    assert _OBS_WEIGHT_BY_QTYPE["behavioral_probe"] == 0.00
    assert _OBS_WEIGHT_BY_QTYPE["technical_concept"] > 0
    assert _OBS_WEIGHT_BY_QTYPE["project_deep_dive"] > 0
    for qt, w in _OBS_WEIGHT_BY_QTYPE.items():
        assert 0.0 <= w <= 1.0, f"{qt}: weight {w} out of range"
