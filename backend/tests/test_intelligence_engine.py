"""Tests for the Phase 11 intelligence engine."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from agents.intelligence_engine import (
    build_interview_plan,
    initialize_candidate_state,
    update_candidate_state,
    make_next_question_decision,
)
from models.agent_state import CandidateState, InterviewPlanItem


# ── Minimal stub for ResumeAnalysis ──────────────────────────────────────────

class _Project:
    def __init__(self, name, technologies=None):
        self.name = name
        self.technologies = technologies or []


class _FakeAnalysis:
    def __init__(
        self,
        skills=None,
        strengths=None,
        weak_areas=None,
        projects=None,
        experience_level="mid",
        domains=None,
    ):
        self.skills = skills or []
        self.strengths = strengths or []
        self.weak_areas = weak_areas or []
        self.projects = projects or []
        self.experience_level = experience_level
        self.domains = domains or []


# ── build_interview_plan ──────────────────────────────────────────────────────

class TestBuildInterviewPlan:
    def test_returns_list_of_plan_items(self):
        analysis = _FakeAnalysis(
            skills=["React", "Node.js"],
            projects=[_Project("My App", ["React", "Node.js"])],
        )
        plan = build_interview_plan(analysis, "Full Stack Developer")
        assert isinstance(plan, list)
        assert len(plan) >= 3
        assert all(isinstance(item, InterviewPlanItem) for item in plan)

    def test_first_step_is_project_deep_dive(self):
        analysis = _FakeAnalysis(
            projects=[_Project("Portfolio", ["React"])],
        )
        plan = build_interview_plan(analysis, "Full Stack Developer")
        assert plan[0].topic == "Project Deep Dive"

    def test_step_numbers_are_sequential(self):
        analysis = _FakeAnalysis()
        plan = build_interview_plan(analysis, "Backend Developer")
        for i, item in enumerate(plan):
            assert item.step == i + 1

    def test_plan_has_at_most_five_steps(self):
        analysis = _FakeAnalysis(
            skills=["Python", "FastAPI", "PostgreSQL"],
            projects=[_Project("API Service", ["FastAPI"])],
        )
        plan = build_interview_plan(analysis, "Backend Developer")
        assert len(plan) <= 5

    def test_difficulty_field_is_valid(self):
        analysis = _FakeAnalysis()
        plan = build_interview_plan(analysis, "Frontend Developer")
        valid_difficulties = {"easy", "medium", "hard"}
        for item in plan:
            assert item.difficulty in valid_difficulties

    def test_unknown_role_still_produces_plan(self):
        analysis = _FakeAnalysis()
        plan = build_interview_plan(analysis, "Unknown Role XYZ")
        assert len(plan) >= 3

    def test_none_analysis_still_produces_plan(self):
        plan = build_interview_plan(None, "Full Stack Developer")
        assert len(plan) >= 3

    def test_weak_areas_appear_in_plan(self):
        analysis = _FakeAnalysis(
            weak_areas=["Authentication"],
            projects=[_Project("Demo", [])],
        )
        plan = build_interview_plan(analysis, "Full Stack Developer")
        topics = [item.topic for item in plan]
        # Authentication is mapped to a curriculum topic; some plan item reason should mention it
        reasons_and_evidence = " ".join(
            item.reason + " ".join(item.linked_resume_evidence)
            for item in plan
        )
        assert "Authentication" in reasons_and_evidence or "Authentication" in topics

    def test_plan_items_have_evidence(self):
        analysis = _FakeAnalysis(
            skills=["React", "CSS"],
            projects=[_Project("Site", ["React"])],
        )
        plan = build_interview_plan(analysis, "Frontend Developer")
        for item in plan:
            assert isinstance(item.linked_resume_evidence, list)
            assert len(item.linked_resume_evidence) >= 1


# ── initialize_candidate_state ────────────────────────────────────────────────

class TestInitializeCandidateState:
    def _make_plan(self):
        return [
            InterviewPlanItem(
                step=1, topic="Project Deep Dive", difficulty="easy",
                reason="", linked_resume_evidence=[], target_skill=""
            ),
            InterviewPlanItem(
                step=2, topic="API Design", difficulty="medium",
                reason="", linked_resume_evidence=[], target_skill=""
            ),
        ]

    def test_returns_candidate_state(self):
        analysis = _FakeAnalysis(skills=["Python"])
        plan = self._make_plan()
        state = initialize_candidate_state("sess1", "cand1", "Backend Developer", analysis, plan)
        assert isinstance(state, CandidateState)

    def test_session_and_candidate_ids_preserved(self):
        analysis = _FakeAnalysis()
        plan = self._make_plan()
        state = initialize_candidate_state("s123", "c456", "Backend Developer", analysis, plan)
        assert state.session_id == "s123"
        assert state.candidate_id == "c456"

    def test_skill_mastery_initialised_for_plan_topics(self):
        analysis = _FakeAnalysis(skills=["FastAPI"])
        plan = self._make_plan()
        state = initialize_candidate_state("s1", "c1", "Backend Developer", analysis, plan)
        assert "Project Deep Dive" in state.skill_mastery
        assert "API Design" in state.skill_mastery

    def test_mastery_values_in_valid_range(self):
        analysis = _FakeAnalysis(
            skills=["Python", "Docker"],
            strengths=["API Design"],
            weak_areas=["Concurrency"],
        )
        plan = self._make_plan()
        state = initialize_candidate_state("s1", "c1", "Backend Developer", analysis, plan)
        for topic, score in state.skill_mastery.items():
            assert 0 <= score <= 100, f"Mastery for '{topic}' out of range: {score}"

    def test_senior_gets_higher_mastery_than_junior(self):
        senior_analysis = _FakeAnalysis(experience_level="senior")
        junior_analysis = _FakeAnalysis(experience_level="junior")
        plan = self._make_plan()
        senior_state = initialize_candidate_state("s1", "c1", "Backend Developer", senior_analysis, plan)
        junior_state = initialize_candidate_state("s2", "c2", "Backend Developer", junior_analysis, plan)
        senior_total = sum(senior_state.skill_mastery.values())
        junior_total = sum(junior_state.skill_mastery.values())
        assert senior_total >= junior_total

    def test_inferred_level_is_valid(self):
        for level in ("junior", "mid", "senior"):
            analysis = _FakeAnalysis(experience_level=level)
            plan = self._make_plan()
            state = initialize_candidate_state("s", "c", "Backend Developer", analysis, plan)
            assert state.inferred_level == level

    def test_none_analysis_produces_valid_state(self):
        plan = self._make_plan()
        state = initialize_candidate_state("s", "c", "Backend Developer", None, plan)
        assert isinstance(state, CandidateState)
        assert state.inferred_level == "mid"


# ── update_candidate_state ────────────────────────────────────────────────────

class TestUpdateCandidateState:
    def _base_state(self):
        return CandidateState(
            session_id="s1",
            candidate_id="c1",
            selected_role="Backend Developer",
            inferred_level="mid",
            strong_skills=["Python"],
            weak_skills=[],
            skill_mastery={"API Design": 50, "Database": 50},
            confidence_trend="unknown",
            communication_trend="unknown",
            risk_flags=[],
            last_decision="",
            next_best_action="",
        )

    def test_returns_candidate_state(self):
        state = self._base_state()
        record = {"topic": "API Design", "answer_text": "I used FastAPI", "evaluation": {"technical_score": 70, "depth_score": 60}}
        result = update_candidate_state(state, record)
        assert isinstance(result, CandidateState)

    def test_high_score_sets_improving_trend(self):
        state = self._base_state()
        record = {"topic": "API Design", "answer_text": "detailed answer " * 10, "evaluation": {"technical_score": 85, "depth_score": 80}}
        result = update_candidate_state(state, record)
        assert result.confidence_trend == "improving"

    def test_low_score_adds_risk_flag(self):
        state = self._base_state()
        record = {"topic": "Database", "answer_text": "I don't know", "evaluation": {"technical_score": 30, "depth_score": 20}}
        result = update_candidate_state(state, record)
        assert any("Database" in f for f in result.risk_flags)

    def test_mastery_updated_for_topic(self):
        state = self._base_state()
        prior = state.skill_mastery["API Design"]
        record = {"topic": "API Design", "answer_text": "Good answer " * 20, "evaluation": {"technical_score": 90, "depth_score": 85}}
        result = update_candidate_state(state, record)
        # Mastery should shift toward 90
        assert result.skill_mastery["API Design"] != prior or prior == 90

    def test_very_brief_answer_adds_risk_flag(self):
        state = self._base_state()
        record = {"topic": "API Design", "answer_text": "yes", "evaluation": {"technical_score": 70, "depth_score": 60}}
        result = update_candidate_state(state, record)
        assert any("brief" in f.lower() for f in result.risk_flags)

    def test_original_state_not_mutated(self):
        state = self._base_state()
        original_mastery = dict(state.skill_mastery)
        record = {"topic": "API Design", "answer_text": "answer", "evaluation": {"technical_score": 60, "depth_score": 50}}
        update_candidate_state(state, record)
        assert state.skill_mastery == original_mastery


# ── make_next_question_decision ───────────────────────────────────────────────

class TestMakeNextQuestionDecision:
    def _base_state(self):
        return CandidateState(
            session_id="s1",
            candidate_id="c1",
            selected_role="Backend Developer",
            inferred_level="mid",
            strong_skills=[],
            weak_skills=[],
            skill_mastery={"API Design": 60, "Database": 55, "Concurrency": 50},
            confidence_trend="stable",
            communication_trend="good",
            risk_flags=[],
            last_decision="",
            next_best_action="",
        )

    def _plan(self):
        return [
            InterviewPlanItem(step=1, topic="Project Deep Dive", difficulty="easy", reason="", linked_resume_evidence=[], target_skill=""),
            InterviewPlanItem(step=2, topic="API Design", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
            InterviewPlanItem(step=3, topic="Database", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
        ]

    def test_returns_agent_decision_trace(self):
        from models.agent_state import AgentDecisionTrace
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 70, "depth_score": 65, "missing_points": [], "covered_points": ["REST"]},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
        )
        assert isinstance(result, AgentDecisionTrace)

    def test_high_score_triggers_increase_difficulty(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 85, "depth_score": 80, "missing_points": [], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
        )
        assert result.decision_type == "increase_difficulty"

    def test_low_score_triggers_strengthen_fundamentals(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 35, "depth_score": 30, "missing_points": ["REST basics", "HTTP verbs"], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
        )
        assert result.decision_type == "strengthen_fundamentals"

    def test_mid_score_triggers_deeper_follow_up(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 65, "depth_score": 60, "missing_points": [], "covered_points": ["REST"]},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
        )
        assert result.decision_type in ("deeper_follow_up",)

    def test_repeated_weakness_triggers_remediation(self):
        state = self._base_state()
        state.risk_flags = ["Repeated weakness on 'API Design' — needs remediation"]
        result = make_next_question_decision(
            state,
            {"technical_score": 40, "depth_score": 35, "missing_points": [], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
        )
        assert result.decision_type == "remediation"

    def test_decision_trace_has_evidence_list(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 70, "depth_score": 65, "missing_points": [], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
        )
        assert isinstance(result.evidence, list)
        assert len(result.evidence) >= 2

    def test_next_topic_comes_from_plan(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 75, "depth_score": 70, "missing_points": [], "covered_points": []},
            {"topic": "Project Deep Dive", "difficulty": "easy"},
            self._plan(),
            [],
        )
        # Next topic should be one from the plan (not already covered)
        plan_topics = {"Project Deep Dive", "API Design", "Database"}
        assert result.next_topic in plan_topics
