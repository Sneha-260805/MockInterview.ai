"""
Phase 1 — Question Mix Policy tests.

Covers:
  1. Plan with projects → first step is project_deep_dive
  2. Plan caps project questions at ≤ 2
  3. Plan contains ≥ 3 technical_concept steps
  4. Redis / API / Auth / RAG-style topics classified as concept (not project)
  5. verify_resume_claim redirected when project quota exhausted
  6. Behavioral probe remains signal-driven (not counted as concept)
  7. question_generator prompt includes question_type_hint
"""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.intelligence_engine import (
    classify_question_category,
    count_question_categories,
    should_allow_project_question,
    should_prioritize_concept_question,
    build_interview_plan,
    make_next_question_decision,
)
from models.agent_state import CandidateState, InterviewPlanItem


# ── Minimal resume fixture ────────────────────────────────────────────────────

def _make_project(name: str, techs: list[str]):
    p = MagicMock()
    p.name = name
    p.technologies = techs
    p.domain = None
    return p


def _make_analysis(*, has_projects: bool = True, weak_areas: list[str] | None = None):
    analysis = MagicMock()
    analysis.skills = ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"]
    analysis.projects = (
        [_make_project("RAG Chatbot", ["Python", "LangChain", "Redis"])] if has_projects else []
    )
    analysis.strengths = ["Python backend development"]
    analysis.weak_areas = weak_areas or []
    analysis.domains = ["backend"]
    analysis.experience_level = "mid"
    return analysis


def _make_candidate_state(**overrides) -> CandidateState:
    defaults = dict(
        session_id="s1",
        candidate_id="c1",
        selected_role="Backend Developer",
        inferred_level="mid",
        strong_skills=["Python", "FastAPI"],
        weak_skills=[],
        skill_mastery={"Project Deep Dive": 55, "API Design": 60, "Database": 58},
        confidence_trend="stable",
        communication_trend="good",
        risk_flags=[],
        last_decision="session_start",
        next_best_action="API Design",
        answers_answered=2,
        concept_gaps={},
        domain_performance={},
    )
    defaults.update(overrides)
    return CandidateState(**defaults)


def _make_plan(*steps: tuple[str, str]) -> list[InterviewPlanItem]:
    return [
        InterviewPlanItem(
            step=i + 1,
            topic=t,
            difficulty="medium",
            reason="test",
            linked_resume_evidence=[],
            target_skill=t,
            question_type=qt,
        )
        for i, (t, qt) in enumerate(steps)
    ]


# ── Test 1: Plan with projects opens with project_deep_dive ──────────────────

def test_plan_with_project_has_initial_project_deep_dive():
    analysis = _make_analysis(has_projects=True)
    plan = build_interview_plan(analysis, "Backend Developer")
    assert len(plan) >= 1
    assert plan[0].topic == "Project Deep Dive"
    assert plan[0].question_type == "project_deep_dive"


# ── Test 2: Plan limits project questions to ≤ 2 ─────────────────────────────

def test_plan_limits_project_questions_to_max_two():
    analysis = _make_analysis(has_projects=True)
    plan = build_interview_plan(analysis, "Backend Developer")
    counts = count_question_categories(plan)
    assert counts["project"] <= 2, (
        f"Plan has {counts['project']} project questions; expected ≤ 2"
    )


# ── Test 3: Plan contains ≥ 3 technical_concept steps ────────────────────────

def test_plan_prioritizes_at_least_three_concept_questions():
    analysis = _make_analysis(has_projects=True)
    plan = build_interview_plan(analysis, "Backend Developer")
    counts = count_question_categories(plan)
    assert counts["concept"] >= 3, (
        f"Plan has only {counts['concept']} concept questions; expected ≥ 3"
    )


# ── Test 4: Redis / API / Auth / RAG are classified as concept ───────────────

@pytest.mark.parametrize("topic,qt,dt,expected", [
    ("REST Fundamentals", "technical_concept", "", "concept"),
    ("API Design", "technical_concept", "", "concept"),
    ("Authentication", "technical_concept", "", "concept"),
    ("Redis Cache", "technical_concept", "verify_resume_claim", "concept"),
    ("RAG Pipeline", "technical_concept", "verify_resume_claim", "concept"),
    ("Database", "technical_concept", "deeper_follow_up", "concept"),
    ("Project Deep Dive", "project_deep_dive", "", "project"),
    ("Project Deep Dive", "", "verify_resume_claim", "project"),
    ("Behavioral & Communication", "behavioral", "", "behavioral"),
    ("Behavioral & Communication", "", "behavioral_probe", "behavioral"),
])
def test_redis_api_auth_rag_followups_classified_as_concept(topic, qt, dt, expected):
    result = classify_question_category(topic=topic, question_type=qt, decision_type=dt)
    assert result == expected, (
        f"classify_question_category({topic!r}, {qt!r}, {dt!r}) = {result!r}; expected {expected!r}"
    )


# ── Test 5: verify_resume_claim redirected when project quota exhausted ───────

def test_project_quota_exhausted_blocks_extra_claim_verification():
    """
    When session_history already has 2 project questions, make_next_question_decision
    must redirect verify_resume_claim → deeper_follow_up.
    """
    candidate_state = _make_candidate_state(answers_answered=3)
    plan = _make_plan(
        ("Project Deep Dive", "project_deep_dive"),
        ("API Design", "technical_concept"),
        ("Database", "technical_concept"),
    )

    # Build a session history that already contains 2 project questions.
    def _hist_entry(topic: str, qt: str):
        return {"question": {"topic": topic, "question_type": qt}, "answer": {}}

    session_history = [
        _hist_entry("Project Deep Dive", "project_deep_dive"),
        _hist_entry("Project Deep Dive", "project_deep_dive"),
    ]

    last_eval = {
        "technical_score": 55,
        "depth_score": 50,
        "missing_points": ["load balancing", "retry logic"],
        "covered_points": [],
    }
    current_question = {"topic": "Project Deep Dive", "difficulty": "easy"}

    trace = make_next_question_decision(
        candidate_state=candidate_state,
        last_evaluation=last_eval,
        current_question=current_question,
        interview_plan=plan,
        session_history=session_history,
    )

    assert trace.decision_type != "verify_resume_claim", (
        f"Expected verify_resume_claim to be redirected but got: {trace.decision_type}"
    )


# ── Test 6: Behavioral probe remains signal-driven ───────────────────────────

def test_behavioral_probe_still_signal_driven():
    """
    With answers_answered < 2 and no trend signals, behavioral_probe must NOT fire.
    """
    candidate_state = _make_candidate_state(
        answers_answered=1,
        communication_trend="unknown",
        confidence_trend="unknown",
    )
    plan = _make_plan(
        ("Project Deep Dive", "project_deep_dive"),
        ("API Design", "technical_concept"),
    )
    last_eval = {
        "technical_score": 70,
        "depth_score": 65,
        "missing_points": [],
        "covered_points": ["REST methods", "status codes"],
    }
    current_question = {"topic": "Project Deep Dive", "difficulty": "easy"}

    trace = make_next_question_decision(
        candidate_state=candidate_state,
        last_evaluation=last_eval,
        current_question=current_question,
        interview_plan=plan,
        session_history=[],
    )

    assert trace.decision_type != "behavioral_probe", (
        f"Behavioral probe fired too early with answers_answered=1 and no signals. "
        f"Got decision_type={trace.decision_type!r}"
    )


# ── Test 7: question_generator prompt includes question_type_hint ─────────────

def test_question_generator_prompt_includes_question_type_hint():
    from services.question_generator import (
        QuestionDecisionContext,
        build_llm_prompt,
    )
    from unittest.mock import MagicMock

    ctx = QuestionDecisionContext(
        decision_type="project_deep_dive",
        decision_reason="Opening with project deep dive.",
        question_type_hint="project_deep_dive",
    )
    prompt = build_llm_prompt(
        role="Backend Developer",
        topic="Project Deep Dive",
        difficulty="easy",
        analysis=None,
        ctx=ctx,
    )
    assert "question_type_hint" in prompt, "Prompt must contain 'question_type_hint'"
    assert "project_deep_dive" in prompt, "Prompt must contain the hint value 'project_deep_dive'"
