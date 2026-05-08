"""Tests for the rule-based scoring service."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.scoring_service import keyword_coverage


class TestKeywordCoverage:
    def test_full_coverage(self):
        answer = "I used React hooks and useState for state management with useEffect for side effects"
        points = ["React hooks", "state management", "useEffect"]
        ratio, covered, missing = keyword_coverage(answer, points)
        assert ratio == 1.0
        assert set(covered) == set(points)
        assert missing == []

    def test_no_coverage(self):
        answer = "I used Vue.js and Vuex for all state handling"
        points = ["React hooks", "Redux", "useEffect"]
        ratio, covered, missing = keyword_coverage(answer, points)
        assert ratio == 0.0
        assert covered == []
        assert len(missing) == 3

    def test_partial_coverage(self):
        answer = "I used React for the frontend components"
        points = ["React", "Node.js", "MongoDB"]
        ratio, covered, missing = keyword_coverage(answer, points)
        assert 0 < ratio < 1.0
        assert "React" in covered
        assert len(missing) == 2

    def test_empty_expected_points_returns_full_coverage(self):
        ratio, covered, missing = keyword_coverage("any answer here", [])
        assert ratio == 1.0
        assert covered == []
        assert missing == []

    def test_prefix_matching_for_long_terms(self):
        # "authenticate" shares a 6-char prefix with "authentication"
        answer = "I implement authentication using JWT tokens and session management"
        points = ["authentication"]
        ratio, covered, missing = keyword_coverage(answer, points)
        assert ratio == 1.0
        assert "authentication" in covered

    def test_case_insensitive(self):
        answer = "PYTHON and DJANGO are my main backend tools"
        points = ["Python", "Django"]
        ratio, covered, missing = keyword_coverage(answer, points)
        assert ratio == 1.0

    def test_stopwords_ignored(self):
        # Point containing only stopwords should still match
        answer = "I work with databases"
        points = ["databases"]
        ratio, covered, _ = keyword_coverage(answer, points)
        assert ratio == 1.0
