"""Tests for the Phase 11 rubric scoring service."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.rubric_service import score_with_rubric


class TestScoreWithRubric:
    def test_returns_all_required_keys(self):
        result = score_with_rubric("I used React hooks for state management", "React & Hooks", [])
        assert "rubric_scores" in result
        assert "rubric_total" in result
        assert "evidence" in result
        assert "improvement_hint" in result
        assert "interviewer_diagnosis" in result

    def test_scores_are_dicts(self):
        result = score_with_rubric("Some answer text", "Python Basics", [])
        assert isinstance(result["rubric_scores"], dict)
        assert isinstance(result["evidence"], list)

    def test_total_within_bounds(self):
        result = score_with_rubric(
            "I optimised database queries using indexing and caching strategies in my project",
            "Databases & SQL", []
        )
        assert 0 <= result["rubric_total"] <= 100

    def test_empty_answer_scores_zero(self):
        result = score_with_rubric("", "Python Basics", [])
        assert result["rubric_total"] == 0

    def test_rich_answer_scores_higher_than_weak(self):
        weak_result = score_with_rubric("I used Python", "Python Basics", [])
        strong_result = score_with_rubric(
            "In my backend project I used Python with FastAPI to build async REST APIs. "
            "The key trade-off was choosing async over sync because we needed high concurrency "
            "with 10,000 concurrent connections. I implemented proper error handling, "
            "Pydantic validation, and unit tests with pytest achieving 90% coverage.",
            "Python Basics", []
        )
        assert strong_result["rubric_total"] >= weak_result["rubric_total"]

    def test_dimension_scores_sum_near_total(self):
        result = score_with_rubric(
            "I built a REST API using FastAPI with authentication and database integration",
            "APIs & REST", []
        )
        scores = result["rubric_scores"]
        total_from_dims = sum(scores.values())
        # Total should match or be close to sum of dimensions
        assert abs(result["rubric_total"] - total_from_dims) <= 1

    def test_improvement_hint_is_string(self):
        result = score_with_rubric("short answer", "System Design", [])
        assert isinstance(result["improvement_hint"], str)
        assert len(result["improvement_hint"]) > 0

    def test_evidence_items_are_strings(self):
        result = score_with_rubric(
            "I used caching, indexing, and database optimisation techniques",
            "Databases & SQL", []
        )
        for item in result["evidence"]:
            assert isinstance(item, str)
