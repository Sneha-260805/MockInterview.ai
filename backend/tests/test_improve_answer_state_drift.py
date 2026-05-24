"""
Tests for /improve-answer state drift + double-counting fix (STEP 5, revised).

Verified double-counting bugs that were fixed:
  1. answers_answered was incorrectly incremented by improve-answer.
  2. domain_performance appended a second entry for the same question,
     which could falsely trigger persistent_weak → remediation.
  3. concept_gaps were never reduced when a previously-missing concept was covered.
  4. risk_flags retained stale weak-performance flags after improvement.

The fix: update_candidate_state_for_improvement() replaces the generic
update_candidate_state() call in /improve-answer.
"""

import pytest
from models.interview import EvaluationResult
from models.agent_state import CandidateState
from agents import intelligence_engine


# ── Shared fixtures ────────────────────────────────────────────────────────────

def _make_state(*, answers_answered: int = 0, extra_mastery: dict | None = None) -> CandidateState:
    mastery = {"Database": 50, "API Design": 45, "Concurrency": 55}
    if extra_mastery:
        mastery.update(extra_mastery)
    return CandidateState(
        session_id="session-test",
        candidate_id="cand-test",
        selected_role="Backend Developer",
        inferred_level="mid",
        strong_skills=["Python", "SQL"],
        weak_skills=["System Design"],
        skill_mastery=mastery,
        confidence_trend="unknown",
        communication_trend="unknown",
        risk_flags=[],
        last_decision="session_start",
        next_best_action="Database",
        answers_answered=answers_answered,
    )


def _weak_eval() -> dict:
    return EvaluationResult(
        technical_score=40,
        depth_score=35,
        correctness_score=38,
        covered_points=["connection pooling"],
        missing_points=["query optimization", "indexing"],
        feedback="Weak answer.",
        evaluation_mode="rule_based",
        evaluation_provider="rule_based",
    ).model_dump()


def _improved_eval() -> dict:
    return EvaluationResult(
        technical_score=72,
        depth_score=68,
        correctness_score=70,
        covered_points=["connection pooling", "query optimization", "indexing"],
        missing_points=[],
        feedback="Much better.",
        evaluation_mode="rule_based",
        evaluation_provider="rule_based",
    ).model_dump()


def _still_weak_eval() -> dict:
    """Improved but still below 50 — tests persistent_weak protection."""
    return EvaluationResult(
        technical_score=48,
        depth_score=42,
        correctness_score=44,
        covered_points=["connection pooling"],
        missing_points=["query optimization", "indexing"],
        feedback="Slightly better but still weak.",
        evaluation_mode="rule_based",
        evaluation_provider="rule_based",
    ).model_dump()


def _answer_record(eval_dict: dict, attempt_number: int = 1) -> dict:
    return {
        "question_id": "q1",
        "question": "How do you optimize database queries?",
        "answer_text": "Use connection pooling." * (5 if attempt_number == 1 else 15),
        "evaluation": eval_dict,
        "topic": "Database",
        "attempt_number": attempt_number,
    }


# ── A. answers_answered must not increment ────────────────────────────────────

class TestAnswersAnsweredNotIncremented:
    """Test A: improve-answer does not increase unique answered question count."""

    def test_answers_answered_stays_at_one_after_improvement(self):
        """answers_answered should equal number of unique questions (1), not retries."""
        state = _make_state()

        # First genuine answer (unique Q1)
        state_after_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval(), attempt_number=1),
        )
        assert state_after_q1.answers_answered == 1, (
            f"After Q1 answered: expected 1, got {state_after_q1.answers_answered}"
        )

        # Improve Q1 — same unique question, just retried
        state_after_improve = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_after_q1,
            answer_record=_answer_record(_improved_eval(), attempt_number=2),
            previous_evaluation=_weak_eval(),
        )
        assert state_after_improve.answers_answered == 1, (
            f"After improving Q1: answers_answered should still be 1, "
            f"got {state_after_improve.answers_answered}"
        )

    def test_second_real_question_increments_correctly(self):
        """After improve-answer keeps count at 1, a real new Q increments to 2."""
        state = _make_state()

        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval(), attempt_number=1),
        )
        state_improved = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_improved_eval(), attempt_number=2),
            previous_evaluation=_weak_eval(),
        )

        q2_record = {
            "question_id": "q2",
            "question": "Explain REST API design principles.",
            "answer_text": "REST uses stateless communication with JSON over HTTP. " * 8,
            "evaluation": _improved_eval(),
            "topic": "API Design",
            "attempt_number": 1,
        }
        state_q2 = intelligence_engine.update_candidate_state(
            candidate_state=state_improved,
            answer_record=q2_record,
        )
        assert state_q2.answers_answered == 2, (
            f"After Q2 answered: expected 2, got {state_q2.answers_answered}"
        )


# ── B. MAX_QUESTIONS / session progress not advanced ─────────────────────────

class TestMaxQuestionsNotAdvanced:
    """Test B: improve-answer does not make session closer to MAX_QUESTIONS."""

    def test_last_decision_is_improvement_update_not_post_answer(self):
        """
        last_decision differentiates improve-answer updates from new-question updates.
        Routes should not count improve-answer as progress toward session completion.
        """
        state = _make_state()
        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval()),
        )
        assert state_q1.last_decision == "post_answer_update"

        state_improved = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_improved_eval(), attempt_number=2),
            previous_evaluation=_weak_eval(),
        )
        assert state_improved.last_decision == "improvement_update", (
            "improve-answer state update must be marked 'improvement_update', not 'post_answer_update'"
        )

    def test_answers_answered_unchanged_multiple_retries(self):
        """Even two retries (attempt 2 then 3) do not advance answers_answered past 1."""
        state = _make_state()

        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval(), attempt_number=1),
        )
        state_retry1 = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_still_weak_eval(), attempt_number=2),
            previous_evaluation=_weak_eval(),
        )
        state_retry2 = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_retry1,
            answer_record=_answer_record(_improved_eval(), attempt_number=3),
            previous_evaluation=_still_weak_eval(),
        )
        assert state_retry2.answers_answered == 1, (
            f"After two retries: answers_answered should still be 1, "
            f"got {state_retry2.answers_answered}"
        )


# ── C. domain_performance replaces, not appends ───────────────────────────────

class TestDomainPerformanceNoDoubleEntry:
    """Test C: score trend entry for a topic is replaced, not duplicated."""

    def test_domain_performance_has_one_entry_after_improvement(self):
        """Domain history for Q1's topic must have exactly 1 score after improve."""
        state = _make_state()
        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval()),
        )
        assert state_q1.domain_performance.get("Database") == [40], (
            f"Unexpected domain_performance after Q1: {state_q1.domain_performance}"
        )

        state_improved = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_improved_eval(), attempt_number=2),
            previous_evaluation=_weak_eval(),
        )
        db_history = state_improved.domain_performance.get("Database", [])
        assert len(db_history) == 1, (
            f"domain_performance['Database'] should have 1 entry (replaced, not appended), "
            f"got {db_history}"
        )
        assert db_history[0] == 72, (
            f"domain_performance should hold the improved score (72), got {db_history}"
        )

    def test_persistent_weak_not_falsely_triggered_after_improvement(self):
        """
        Critical: if weak=40, improved=48, appending would create [40, 48] → avg=44 < 50
        → persistent_weak=True → wrongly triggers remediation.
        Replacing keeps [48] → no persistent_weak.
        """
        state = _make_state()
        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval()),   # score 40
        )
        state_improved = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_still_weak_eval(), attempt_number=2),  # score 48
            previous_evaluation=_weak_eval(),
        )
        db_history = state_improved.domain_performance.get("Database", [])
        # With replace-not-append, history has only [48], so persistent_weak check
        # (requires len >= 2) cannot fire.
        assert len(db_history) == 1, (
            f"Replace-not-append broken: history is {db_history}; "
            "this would cause false persistent_weak → remediation"
        )
        assert db_history[0] == 48


# ── D. next-question after improve-answer uses improved state ─────────────────

class TestNextQuestionUsesImprovedState:
    """Test D: next-question decision sees the improved candidate_state."""

    def test_skill_mastery_reflects_improved_score(self):
        """
        Mastery after improve-answer should be higher than after the weak answer,
        and the improved state is what /next-question receives.
        """
        state = _make_state()
        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval()),
        )
        weak_mastery = state_q1.skill_mastery["Database"]

        state_improved = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_improved_eval(), attempt_number=2),
            previous_evaluation=_weak_eval(),
        )
        improved_mastery = state_improved.skill_mastery["Database"]

        assert improved_mastery > weak_mastery, (
            f"Improved mastery ({improved_mastery}) should exceed weak mastery ({weak_mastery})"
        )
        # answers_answered is 1 — the next-question handler sees exactly one question answered
        assert state_improved.answers_answered == 1

    def test_concept_gaps_reduced_after_improvement(self):
        """
        Concepts that were missing in the original answer but covered in the improved
        answer should have their gap count decremented (not permanently stuck).
        """
        state = _make_state()
        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval()),
        )
        assert "query optimization" in state_q1.concept_gaps
        assert "indexing" in state_q1.concept_gaps

        state_improved = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_improved_eval(), attempt_number=2),
            previous_evaluation=_weak_eval(),
        )
        # improved_eval covers both previously-missing concepts → gaps should be cleared
        assert "query optimization" not in state_improved.concept_gaps, (
            "Covered concept 'query optimization' should be removed from concept_gaps"
        )
        assert "indexing" not in state_improved.concept_gaps, (
            "Covered concept 'indexing' should be removed from concept_gaps"
        )

    def test_risk_flags_cleared_after_strong_improvement(self):
        """Stale weak-performance flag for a topic is removed when score improves >= 50."""
        state = _make_state()
        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval()),
        )
        assert any("'Database'" in f for f in state_q1.risk_flags), (
            "Weak answer should produce a risk flag for 'Database'"
        )

        state_improved = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_improved_eval(), attempt_number=2),
            previous_evaluation=_weak_eval(),
        )
        stale_flags = [f for f in state_improved.risk_flags if "'Database'" in f]
        assert not stale_flags, (
            f"Stale weak flag should be cleared after score improves to 72, "
            f"but found: {stale_flags}"
        )

    def test_weak_flag_retained_when_still_weak(self):
        """If improved score is still < 50, a risk flag should remain (refreshed)."""
        state = _make_state()
        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval()),   # score 40
        )
        state_improved = intelligence_engine.update_candidate_state_for_improvement(
            candidate_state=state_q1,
            answer_record=_answer_record(_still_weak_eval(), attempt_number=2),  # score 48
            previous_evaluation=_weak_eval(),
        )
        weak_flags = [f for f in state_improved.risk_flags if "'Database'" in f]
        assert weak_flags, (
            "A risk flag should remain for 'Database' when improved score is still < 50"
        )


# ── Backward-compatible: update_candidate_state still works normally ──────────

class TestExistingUpdateUnchanged:
    """Verify that the original update_candidate_state() is unchanged."""

    def test_normal_update_still_increments_answers_answered(self):
        state = _make_state()
        updated = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_improved_eval()),
        )
        assert updated.answers_answered == 1

    def test_normal_update_appends_domain_performance(self):
        state = _make_state()
        updated = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_improved_eval()),
        )
        assert updated.domain_performance.get("Database") == [72]

    def test_two_real_questions_produce_two_domain_entries(self):
        state = _make_state()
        state_q1 = intelligence_engine.update_candidate_state(
            candidate_state=state,
            answer_record=_answer_record(_weak_eval()),
        )
        q2_record = {
            "question_id": "q2",
            "question": "Explain indexing strategies.",
            "answer_text": "B-tree indexes speed up lookups at the cost of write overhead. " * 5,
            "evaluation": _still_weak_eval(),
            "topic": "Database",
            "attempt_number": 1,
        }
        state_q2 = intelligence_engine.update_candidate_state(
            candidate_state=state_q1,
            answer_record=q2_record,
        )
        # Two real questions on the same topic → two entries [40, 48]
        assert state_q2.domain_performance.get("Database") == [40, 48], (
            f"Two real questions should produce two entries: {state_q2.domain_performance}"
        )
