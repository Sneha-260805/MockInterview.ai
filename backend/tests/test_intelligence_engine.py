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

    def test_next_topic_comes_from_plan_on_switch(self):
        """Solid answer with no gaps should switch to next uncovered plan topic."""
        state = self._base_state()
        history = [
            {"question": {"topic": "Project Deep Dive", "difficulty": "easy"}},
        ]
        result = make_next_question_decision(
            state,
            {"technical_score": 75, "depth_score": 70, "missing_points": [], "covered_points": ["architecture"]},
            {"topic": "Project Deep Dive", "difficulty": "easy"},
            self._plan(),
            history,
        )
        assert result.decision_type == "switch_topic"
        assert result.next_topic == "API Design"
        assert "uncovered" in result.topic_rationale.lower() or "moving" in result.topic_rationale.lower()

    def test_deeper_follow_up_keeps_current_topic(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {
                "technical_score": 65,
                "depth_score": 60,
                "missing_points": ["idempotency keys", "retry strategy"],
                "covered_points": ["REST basics"],
            },
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
        )
        assert result.decision_type == "deeper_follow_up"
        assert result.next_topic == "API Design"
        rationale = result.topic_rationale.lower()
        assert any(w in rationale for w in ("stay", "follow-up", "follow up", "deeper", "probe"))
        assert result.next_question_strategy == "same_topic_depth_probe"

    def test_remediation_uses_weakest_or_gap_topic(self):
        state = CandidateState(
            session_id="s1",
            candidate_id="c1",
            selected_role="Backend Developer",
            inferred_level="mid",
            strong_skills=[],
            weak_skills=["Database Indexing"],
            skill_mastery={
                "API Design": 55,
                "Database Indexing": 32,
                "Database": 50,
            },
            confidence_trend="declining",
            communication_trend="fair",
            risk_flags=["Repeated weakness on 'Database Indexing' — needs remediation"],
            last_decision="",
            next_best_action="Database Indexing",
            concept_gaps={"query plan": 2, "index selectivity": 3},
        )
        plan = [
            InterviewPlanItem(step=1, topic="API Design", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
            InterviewPlanItem(step=2, topic="Database Indexing", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
            InterviewPlanItem(step=3, topic="Database", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
        ]
        result = make_next_question_decision(
            state,
            {
                "technical_score": 38,
                "depth_score": 30,
                "missing_points": ["query plan", "index selectivity"],
                "covered_points": [],
            },
            {"topic": "Database Indexing", "difficulty": "medium"},
            plan,
            [{"question": {"topic": "Database Indexing"}}],
        )
        assert result.decision_type == "remediation"
        assert result.next_topic == "Database Indexing"
        assert result.next_difficulty in ("easy", "medium")
        assert any(w in result.topic_rationale.lower() for w in ("weak", "gap", "weakest", "mastery"))

    def test_confidence_recovery_reduces_difficulty(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 58, "depth_score": 55, "missing_points": [], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
            audio_score={"confidence_score": 40, "communication_clarity_score": 42, "mode": "whisper"},
        )
        assert result.decision_type == "confidence_recovery"
        assert result.next_difficulty == "easy"
        assert "confidence" in result.difficulty_rationale.lower()
        assert result.signal_scores.get("confidence") == 40

    def test_increase_difficulty_for_strong_answer(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 88, "depth_score": 82, "missing_points": [], "covered_points": ["REST"]},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
            audio_score={"confidence_score": 85, "communication_clarity_score": 80, "mode": "whisper"},
        )
        assert result.decision_type == "increase_difficulty"
        assert result.next_difficulty == "hard"
        assert result.next_topic == "API Design"
        assert "increase" in result.difficulty_rationale.lower() or "increased" in result.difficulty_rationale.lower()
        assert result.next_question_strategy in (
            "increase_difficulty_same_topic",
            "advance_uncovered_topic",
            "deepen_same_topic_hard",
        )

    def test_increase_difficulty_advances_when_deep_mastery(self):
        state = self._base_state()
        history = [
            {"question": {"topic": "API Design", "difficulty": "medium"}},
            {"question": {"topic": "API Design", "difficulty": "hard"}},
        ]
        result = make_next_question_decision(
            state,
            {"technical_score": 90, "depth_score": 85, "missing_points": [], "covered_points": ["REST", "versioning"]},
            {"topic": "API Design", "difficulty": "hard"},
            self._plan(),
            history,
        )
        assert result.decision_type == "increase_difficulty"
        assert result.next_topic == "Database"
        assert result.next_question_strategy == "advance_uncovered_topic"

    def test_trace_populates_rationale_fields(self):
        state = self._base_state()
        result = make_next_question_decision(
            state,
            {"technical_score": 65, "depth_score": 60, "missing_points": ["caching"], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [],
        )
        assert result.topic_rationale
        assert result.difficulty_rationale
        assert result.signal_scores.get("technical") == 65
        assert result.next_question_strategy
        assert result.observation
        assert result.generation_mode == "pending"
        assert result.confidence_available is False
        assert result.signal_scores.get("confidence") is None


# ── Step 6: Behavioral probe decision ─────────────────────────────────────────

class TestBehavioralProbeDecision:
    """
    Verify that make_next_question_decision returns decision_type='behavioral_probe'
    in the primary path when conditions are right, and never repeats it.
    """

    def _state_with_n_answered(
        self,
        n: int,
        communication_trend: str = "good",
        confidence_trend: str = "stable",
    ) -> CandidateState:
        return CandidateState(
            session_id="s1",
            candidate_id="c1",
            selected_role="Backend Developer",
            inferred_level="mid",
            strong_skills=["Python"],
            weak_skills=[],
            skill_mastery={"API Design": 65, "Database": 60, "Concurrency": 55},
            confidence_trend=confidence_trend,
            communication_trend=communication_trend,
            risk_flags=[],
            last_decision="post_answer_update",
            next_best_action="Database",
            answers_answered=n,
        )

    def _plan(self):
        return [
            InterviewPlanItem(step=1, topic="Project Deep Dive", difficulty="easy", reason="", linked_resume_evidence=[], target_skill=""),
            InterviewPlanItem(step=2, topic="API Design", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
            InterviewPlanItem(step=3, topic="Database", difficulty="medium", reason="", linked_resume_evidence=[], target_skill=""),
        ]

    def _history_2_technical(self):
        """Two answered technical questions, no behavioral."""
        return [
            {"question": {"topic": "Project Deep Dive", "difficulty": "easy", "question_type": "technical"}},
            {"question": {"topic": "API Design", "difficulty": "medium", "question_type": "technical"}},
        ]

    # ── Test 1 ─────────────────────────────────────────────────────────────────

    def test_behavioral_probe_after_two_technical_answers_with_weak_communication(self):
        """
        After 2 unique technical questions with weak communication trend,
        the primary path should decide behavioral_probe.
        Trace must explain the behavioral rationale.
        """
        state = self._state_with_n_answered(2, communication_trend="poor")
        result = make_next_question_decision(
            state,
            {"technical_score": 65, "depth_score": 60, "missing_points": [], "covered_points": ["REST"]},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            self._history_2_technical(),
        )
        assert result.decision_type == "behavioral_probe", (
            f"Expected behavioral_probe but got {result.decision_type}"
        )
        assert result.next_topic == "Behavioral & Communication"
        assert result.next_difficulty == "medium"
        assert result.next_question_strategy == "behavioral_communication_probe"
        # Trace must explain the why
        assert "behavioral" in result.topic_rationale.lower() or "communication" in result.topic_rationale.lower()
        assert result.observation  # non-empty
        assert "behavioral" in result.detected_issue.lower() or "communication" in result.detected_issue.lower()

    # ── Test 2 ─────────────────────────────────────────────────────────────────

    def test_behavioral_probe_possible_after_strong_technical_performance(self):
        """
        After 3+ questions with strong technical score (>= 75) and good communication,
        behavioral_probe can still trigger to validate ownership and soft skills.
        """
        state = self._state_with_n_answered(3, communication_trend="good", confidence_trend="stable")
        history = [
            {"question": {"topic": "Project Deep Dive", "difficulty": "easy", "question_type": "technical"}},
            {"question": {"topic": "API Design", "difficulty": "medium", "question_type": "technical"}},
            {"question": {"topic": "Database", "difficulty": "medium", "question_type": "technical"}},
        ]
        result = make_next_question_decision(
            state,
            {"technical_score": 82, "depth_score": 75, "missing_points": [], "covered_points": ["indexing"]},
            {"topic": "Database", "difficulty": "medium"},
            self._plan(),
            history,
        )
        assert result.decision_type == "behavioral_probe", (
            f"Expected behavioral_probe for strong candidate at Q4 but got {result.decision_type}"
        )
        assert result.next_topic == "Behavioral & Communication"
        obs = result.observation.lower()
        assert "strong" in obs or "technical" in obs or "score" in obs

    # ── Test 3 ─────────────────────────────────────────────────────────────────

    def test_behavioral_probe_not_repeated(self):
        """
        Once behavioral has been asked (topic in session history),
        the next decision must NOT be behavioral_probe again.
        """
        state = self._state_with_n_answered(3, communication_trend="poor")
        history_with_behavioral = [
            {"question": {"topic": "Project Deep Dive", "difficulty": "easy", "question_type": "technical"}},
            {"question": {"topic": "API Design", "difficulty": "medium", "question_type": "technical"}},
            # Behavioral question already asked
            {"question": {"topic": "Behavioral & Communication", "difficulty": "medium", "question_type": "behavioral"}},
        ]
        result = make_next_question_decision(
            state,
            {"technical_score": 65, "depth_score": 60, "missing_points": [], "covered_points": []},
            {"topic": "Behavioral & Communication", "difficulty": "medium"},
            self._plan(),
            history_with_behavioral,
        )
        assert result.decision_type != "behavioral_probe", (
            "behavioral_probe must not trigger a second time in the same session"
        )

    def test_behavioral_probe_not_triggered_too_early(self):
        """With only 1 unique question answered, behavioral_probe must not fire."""
        state = self._state_with_n_answered(1, communication_trend="poor")
        result = make_next_question_decision(
            state,
            {"technical_score": 65, "depth_score": 60, "missing_points": [], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            [{"question": {"topic": "Project Deep Dive", "difficulty": "easy"}}],
        )
        assert result.decision_type != "behavioral_probe"

    def test_remediation_takes_priority_over_behavioral_probe(self):
        """
        Repeated weakness triggers remediation even when behavioral probe conditions are met.
        Urgent interventions beat behavioral timing.
        """
        state = self._state_with_n_answered(2, communication_trend="poor")
        state.risk_flags = ["Repeated weakness on 'API Design' — needs remediation"]
        result = make_next_question_decision(
            state,
            {"technical_score": 38, "depth_score": 30, "missing_points": ["versioning"], "covered_points": []},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            self._history_2_technical(),
        )
        assert result.decision_type == "remediation", (
            "Remediation must take priority over behavioral probe when repeated weakness exists"
        )

    def test_behavioral_trace_has_required_fields(self):
        """
        Behavioral trace must populate all judge-ready fields.
        Signal: communication_trend='fair' at n=2 is sufficient to trigger behavioral_probe.
        """
        state = self._state_with_n_answered(2, communication_trend="fair")
        result = make_next_question_decision(
            state,
            {"technical_score": 68, "depth_score": 62, "missing_points": [], "covered_points": ["REST"]},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            self._history_2_technical(),
        )
        assert result.decision_type == "behavioral_probe", (
            f"Expected behavioral_probe with comm='fair' signal, got {result.decision_type}"
        )
        assert result.topic_rationale
        assert result.difficulty_rationale
        assert result.next_question_strategy == "behavioral_communication_probe"
        assert result.observation
        assert result.detected_issue
        assert result.reason_for_adaptation
        assert "behavioral" in result.reason_for_adaptation.lower() or "soft" in result.reason_for_adaptation.lower()

    # ── Test 7 ─────────────────────────────────────────────────────────────────

    def test_behavioral_probe_not_triggered_by_two_answers_alone(self):
        """
        answers_answered == 2 is a necessary eligibility gate, NOT a trigger by itself.
        With good communication, stable confidence, and tech_score < 75, behavioral_probe
        must NOT fire at n=2.
        """
        state = self._state_with_n_answered(2, communication_trend="good", confidence_trend="stable")
        result = make_next_question_decision(
            state,
            {"technical_score": 68, "depth_score": 60, "missing_points": ["caching"], "covered_points": ["REST"]},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            self._history_2_technical(),
        )
        assert result.decision_type != "behavioral_probe", (
            f"behavioral_probe must not fire at n=2 without a signal, got {result.decision_type}"
        )

    # ── Test 8 ─────────────────────────────────────────────────────────────────

    def test_behavioral_probe_triggered_by_declining_confidence(self):
        """
        answers_answered == 2 + confidence_trend='declining' is a sufficient signal
        to trigger behavioral_probe, even with good communication and moderate tech score.
        """
        state = self._state_with_n_answered(2, communication_trend="good", confidence_trend="declining")
        result = make_next_question_decision(
            state,
            {"technical_score": 60, "depth_score": 55, "missing_points": [], "covered_points": ["REST"]},
            {"topic": "API Design", "difficulty": "medium"},
            self._plan(),
            self._history_2_technical(),
        )
        assert result.decision_type == "behavioral_probe", (
            f"Expected behavioral_probe with declining confidence signal, got {result.decision_type}"
        )
