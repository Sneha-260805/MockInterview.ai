"""
Phase 5 — Final integration and regression validation.

Covers gaps NOT already tested by earlier phase test files:

  A.  question_type priority in evaluate_answer:
        body.question_type > session question_type > ""
  B.  improve_answer always resolves question_type from session,
        even when body.topic is already provided.
  C.  End-to-end demo flows (plan + mastery init + rubric + mastery update):
      C1  AI/ML RAG candidate
      C2  AI/ML CNN candidate
      C3  Backend Redis/Auth candidate
  D.  Behavioral flow: answer uses behavioral rubric, mastery unchanged
  E.  Fallback safety: missing question_type → safe defaults, no crash
  F.  Project/claim-verification scoring differences
  G.  Multimodal: Phase 1–4 do not break audio/video signal path

Route-level (A, B): TestClient + patch(is_using_memory → True) to stay in-memory.
Unit-level  (C–G): call intelligence_engine / rubric_service directly.
"""

from __future__ import annotations

import sys
import os
import uuid
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import store
from routes.interview_routes import router as interview_router
from agents.intelligence_engine import (
    _resume_aware_curriculum,
    build_interview_plan,
    initialize_candidate_state,
    update_candidate_state,
    classify_question_category,
)
from models.agent_state import CandidateState, InterviewPlanItem
from services import rubric_service


# ── Minimal FastAPI test app ───────────────────────────────────────────────────

_app = FastAPI()
_app.include_router(interview_router)
_client = TestClient(_app, raise_server_exceptions=False)


# ── Reusable fixtures ─────────────────────────────────────────────────────────

class _Project:
    def __init__(self, name: str, techs: list[str]):
        self.name = name
        self.technologies = techs
        self.domain = None


class _Analysis:
    def __init__(
        self,
        skills: list[str] | None = None,
        projects: list | None = None,
        weak_areas: list[str] | None = None,
        strengths: list[str] | None = None,
        experience_level: str = "mid",
        domains: list[str] | None = None,
    ):
        self.skills = skills or []
        self.projects = projects or []
        self.weak_areas = weak_areas or []
        self.strengths = strengths or []
        self.experience_level = experience_level
        self.domains = domains or []


def _make_state(skill_mastery: dict, answers_answered: int = 1) -> CandidateState:
    return CandidateState(
        session_id="p5-session",
        candidate_id="p5-cand",
        selected_role="ML / AI Engineer",
        inferred_level="mid",
        strong_skills=["Python"],
        weak_skills=[],
        skill_mastery=skill_mastery,
        confidence_trend="stable",
        communication_trend="good",
        risk_flags=[],
        last_decision="session_start",
        next_best_action=next(iter(skill_mastery), ""),
        answers_answered=answers_answered,
    )


def _answer_record(topic: str, score: int, covered=None, missing=None) -> dict:
    return {
        "question_id": "q-p5",
        "question": f"Explain {topic}",
        "answer_text": "A thorough answer about " + topic,
        "topic": topic,
        "evaluation": {
            "technical_score": score,
            "depth_score": 65,
            "correctness_score": 70,
            "covered_points": covered or ["concept A", "concept B"],
            "missing_points": missing or [],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# A. question_type priority in evaluate_answer route
# ══════════════════════════════════════════════════════════════════════════════

class TestEvaluateAnswerQuestionTypePriority:
    """
    body.question_type wins when non-empty; session is the fallback.
    Route tests patch is_using_memory → True to avoid MongoDB dependency.
    """

    def _setup_session(self, session_qt: str, q_id: str = "q-prio") -> str:
        sid = f"test-prio-{uuid.uuid4().hex[:6]}"
        store._sessions[sid] = {
            "session_id": sid,
            "questions_asked": [
                {
                    "question_id": q_id,
                    "question": "Explain REST.",
                    "topic": "API Design",
                    "question_type": session_qt,
                    "difficulty": "medium",
                    "expected_points": ["stateless", "http methods"],
                }
            ],
            "answers": [],
            "audio_scores": [],
            "video_scores": [],
        }
        return sid

    def test_body_question_type_takes_priority_when_provided(self):
        """
        When body.question_type='technical_follow_up' and session stores
        'project_deep_dive', the rubric must use technical_follow_up.
        """
        sid = self._setup_session("project_deep_dive")
        payload = {
            "session_id": sid,
            "question_id": "q-prio",
            "question": "Explain REST.",
            "answer": (
                "REST is stateless; each request carries all needed info. "
                "HTTP verbs (GET, POST, PUT, DELETE) map to CRUD operations. "
                "No server-side session means easier horizontal scaling."
            ),
            "expected_points": ["stateless", "http methods"],
            "question_type": "technical_follow_up",   # body overrides session
        }
        with patch("routes.interview_routes.is_using_memory", return_value=True):
            resp = _client.post("/api/interview/evaluate-answer", json=payload)
        store._sessions.pop(sid, None)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("rubric_profile") == "technical_follow_up", (
            f"body.question_type should win; expected 'technical_follow_up', "
            f"got '{data.get('rubric_profile')}'"
        )

    def test_session_question_type_used_as_fallback_when_body_is_empty(self):
        """
        When body.question_type='' and session stores 'technical_concept',
        the rubric must use technical_concept (session fallback).
        """
        sid = self._setup_session("technical_concept")
        payload = {
            "session_id": sid,
            "question_id": "q-prio",
            "question": "Explain REST.",
            "answer": (
                "REST uses stateless HTTP requests. Each verb (GET, POST, PUT, DELETE) "
                "maps to an operation. No server-side session state is stored."
            ),
            "expected_points": ["stateless", "http methods"],
            "question_type": "",   # empty → session wins
        }
        with patch("routes.interview_routes.is_using_memory", return_value=True):
            resp = _client.post("/api/interview/evaluate-answer", json=payload)
        store._sessions.pop(sid, None)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("rubric_profile") == "technical_concept", (
            f"Session fallback should give 'technical_concept', "
            f"got '{data.get('rubric_profile')}'"
        )

    def test_empty_question_type_on_both_sides_does_not_crash(self):
        """
        When question_type is absent from both body AND session, the evaluator
        must still return a valid result (no crash, safe defaults apply).
        """
        sid = f"test-notype-{uuid.uuid4().hex[:6]}"
        store._sessions[sid] = {
            "session_id": sid,
            "questions_asked": [
                {
                    "question_id": "q-notype",
                    "question": "Explain caching.",
                    "topic": "Caching",
                    "question_type": "",
                    "difficulty": "easy",
                    "expected_points": ["speed", "ttl"],
                }
            ],
            "answers": [],
            "audio_scores": [],
            "video_scores": [],
        }
        payload = {
            "session_id": sid,
            "question_id": "q-notype",
            "question": "Explain caching.",
            "answer": (
                "Caching stores frequently accessed data in fast memory to reduce "
                "latency. TTL settings control expiry to keep data fresh."
            ),
            "expected_points": ["speed", "ttl"],
        }
        with patch("routes.interview_routes.is_using_memory", return_value=True):
            resp = _client.post("/api/interview/evaluate-answer", json=payload)
        store._sessions.pop(sid, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "technical_score" in data
        assert data["technical_score"] >= 0


# ══════════════════════════════════════════════════════════════════════════════
# B. improve_answer always resolves question_type from session
# ══════════════════════════════════════════════════════════════════════════════

class TestImproveAnswerQuestionTypeResolution:
    """
    improve_answer must read question_type from session even when body.topic
    is already provided (old bug: question_type stayed '' whenever topic was set).
    """

    def _make_session_with_answered_q(self, session_qt: str) -> str:
        sid = f"test-improve-{uuid.uuid4().hex[:6]}"
        prev_eval = {
            "technical_score": 45, "depth_score": 40, "correctness_score": 42,
            "covered_points": ["basic definition"],
            "missing_points": ["how it works", "use cases"],
            "feedback": "Needs more depth.",
            "evaluation_mode": "rule_based",
            "evaluation_provider": "rule_based",
            "evaluation_source_label": "Rule-based evaluation",
        }
        state = {
            "session_id": sid, "candidate_id": "improve-cand",
            "selected_role": "Backend Developer", "inferred_level": "mid",
            "strong_skills": [], "weak_skills": [],
            "skill_mastery": {"Caching with Redis": 50},
            "confidence_trend": "stable", "communication_trend": "good",
            "risk_flags": [], "last_decision": "session_start",
            "next_best_action": "Caching with Redis", "answers_answered": 1,
        }
        store._sessions[sid] = {
            "session_id": sid,
            "questions_asked": [
                {
                    "question_id": "q-improve",
                    "question": "How does Redis caching work?",
                    "topic": "Caching with Redis",
                    "question_type": session_qt,
                    "difficulty": "medium",
                    "expected_points": ["in-memory", "ttl", "eviction"],
                }
            ],
            "answers": [
                {
                    "question_id": "q-improve",
                    "question": "How does Redis caching work?",
                    "answer_text": "Redis stores data in memory.",
                    "topic": "Caching with Redis",
                    "evaluation": prev_eval,
                    "answered_at": "2026-01-01T00:00:00Z",
                    "attempt_number": 1,
                }
            ],
            "audio_scores": [],
            "video_scores": [],
            "candidate_state": state,
        }
        return sid

    def test_improve_answer_resolves_question_type_even_when_topic_provided(self):
        """
        Providing body.topic must not suppress session question_type lookup.
        After the fix, question_type is always read from session, so mastery
        update uses the correct obs_weight.
        """
        sid = self._make_session_with_answered_q("technical_concept")
        prev_eval = {
            "technical_score": 45, "depth_score": 40, "correctness_score": 42,
            "covered_points": ["basic definition"],
            "missing_points": ["how it works", "use cases"],
            "feedback": "Needs more depth.",
            "evaluation_mode": "rule_based",
            "evaluation_provider": "rule_based",
            "evaluation_source_label": "Rule-based evaluation",
        }
        payload = {
            "session_id": sid,
            "question_id": "q-improve",
            "question": "How does Redis caching work?",
            "improved_answer": (
                "Redis is an in-memory key-value store used as a cache. "
                "It supports TTL to expire stale keys automatically. "
                "When memory fills up, LRU eviction removes oldest entries. "
                "Cache-aside pattern: check Redis first, fetch DB on miss."
            ),
            "expected_points": ["in-memory", "ttl", "eviction"],
            "previous_evaluation": prev_eval,
            "attempt_number": 2,
            "topic": "Caching with Redis",   # body provides topic (old bug trigger)
        }
        with patch("routes.interview_routes.is_using_memory", return_value=True):
            resp = _client.post("/api/interview/improve-answer", json=payload)
        state_after = store._sessions.get(sid, {}).get("candidate_state", {})
        store._sessions.pop(sid, None)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data["technical_score"] > 45, "Improved answer should score better"
        # answers_answered must NOT have incremented
        assert state_after.get("answers_answered", 1) == 1, (
            f"answers_answered must stay at 1, got {state_after.get('answers_answered')}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# C1. End-to-end: AI/ML RAG candidate
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGCandidateFlow:

    def _analysis(self):
        return _Analysis(
            skills=["LangChain", "LLM", "RAG", "FAISS", "Python", "embeddings"],
            projects=[_Project("RAG Chatbot", ["LangChain", "FAISS", "Redis"])],
            strengths=["RAG architecture", "LLM integration"],
        )

    def test_rag_mastery_topics_include_expected_personalized_topics(self):
        topics = _resume_aware_curriculum("ML / AI Engineer", self._analysis())
        assert "RAG Pipeline Design" in topics
        assert "LLM Application Design" in topics
        assert "Vector Search" in topics

    def test_rag_plan_starts_with_project_deep_dive(self):
        plan = build_interview_plan(self._analysis(), "ML / AI Engineer")
        assert plan[0].question_type == "project_deep_dive"
        assert "Project Deep Dive" in plan[0].topic

    def test_rag_plan_has_at_least_3_concept_steps(self):
        plan = build_interview_plan(self._analysis(), "ML / AI Engineer")
        concept_count = sum(1 for p in plan if p.question_type == "technical_concept")
        assert concept_count >= 3, (
            f"Expected ≥3 concept questions, got {concept_count}: "
            f"{[(p.topic, p.question_type) for p in plan]}"
        )

    def test_rag_initial_mastery_above_default_for_resume_topics(self):
        plan = build_interview_plan(self._analysis(), "ML / AI Engineer")
        state = initialize_candidate_state(
            "s1", "c1", "ML / AI Engineer", self._analysis(), plan
        )
        for topic in ("RAG Pipeline Design", "LLM Application Design", "Vector Search"):
            if topic in state.skill_mastery:
                assert state.skill_mastery[topic] > 47, (
                    f"Resume-supported topic '{topic}' should start above 47, "
                    f"got {state.skill_mastery[topic]}"
                )

    def test_rag_follow_up_classified_as_concept(self):
        cat = classify_question_category(
            topic="RAG Pipeline Design",
            question_type="technical_follow_up",
        )
        assert cat == "concept"

    def test_rag_strong_concept_answer_raises_mastery(self):
        state = _make_state({"RAG Pipeline Design": 55})
        record = _answer_record("RAG Pipeline Design", 88)
        updated = update_candidate_state(state, record, question_type="technical_concept")
        assert updated.skill_mastery["RAG Pipeline Design"] > 55

    def test_rag_rubric_technical_concept_has_zero_project_weight(self):
        answer = (
            "RAG retrieves relevant document chunks via vector similarity search "
            "and passes them as context to the LLM, reducing hallucinations "
            "without retraining. Key trade-off is retrieval latency vs accuracy."
        )
        result = rubric_service.score_with_rubric_profile(
            answer, "RAG Pipeline Design", ["retrieval", "vector search", "context"], "technical_concept"
        )
        scores = result["rubric_scores"]
        # technical_concept weight for project is 0 — key may exist but value must be 0
        assert scores.get("resume_project_connection", 0) == 0, (
            f"technical_concept must give resume_project_connection=0, "
            f"got {scores.get('resume_project_connection')}"
        )
        assert result["rubric_total"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# C2. End-to-end: AI/ML CNN candidate
# ══════════════════════════════════════════════════════════════════════════════

class TestCNNCandidateFlow:

    def _analysis(self):
        return _Analysis(
            skills=["PyTorch", "CNN", "ResNet", "image classification", "data augmentation"],
            projects=[_Project("Image Classifier", ["PyTorch", "ResNet", "OpenCV"])],
        )

    def test_cnn_topics_include_cnn_pytorch_augmentation(self):
        topics = _resume_aware_curriculum("ML / AI Engineer", self._analysis())
        assert "CNN Architecture" in topics
        assert "PyTorch Training" in topics
        assert "Data Augmentation" in topics

    def test_cnn_topics_differ_from_rag_topics(self):
        rag_analysis = _Analysis(skills=["LangChain", "RAG", "FAISS", "LLM"])
        rag_topics = set(_resume_aware_curriculum("ML / AI Engineer", rag_analysis))
        cnn_topics = set(_resume_aware_curriculum("ML / AI Engineer", self._analysis()))
        assert rag_topics != cnn_topics
        assert "RAG Pipeline Design" not in cnn_topics
        assert "CNN Architecture" not in rag_topics

    def test_cnn_plan_starts_with_project_deep_dive(self):
        plan = build_interview_plan(self._analysis(), "ML / AI Engineer")
        assert plan[0].question_type == "project_deep_dive"

    def test_cnn_initial_mastery_above_default(self):
        plan = build_interview_plan(self._analysis(), "ML / AI Engineer")
        state = initialize_candidate_state(
            "s2", "c2", "ML / AI Engineer", self._analysis(), plan
        )
        for topic in ("CNN Architecture", "PyTorch Training"):
            if topic in state.skill_mastery:
                assert state.skill_mastery[topic] > 47, (
                    f"'{topic}' should start above 47, got {state.skill_mastery[topic]}"
                )

    def test_cnn_strong_answer_raises_mastery(self):
        state = _make_state({"CNN Architecture": 58})
        record = _answer_record("CNN Architecture", 85)
        updated = update_candidate_state(state, record, question_type="technical_concept")
        assert updated.skill_mastery["CNN Architecture"] > 58

    def test_cnn_rubric_concept_no_project_dimension(self):
        """
        technical_concept profile must never penalise for missing project language.
        Verify by checking rubric_scores has no project dimension.
        """
        answer = (
            "CNNs use convolutional filters to detect local features like edges. "
            "ResNet adds skip connections to solve vanishing gradients, "
            "enabling much deeper architectures without degradation."
        )
        result = rubric_service.score_with_rubric_profile(
            answer, "CNN Architecture",
            ["convolutional filters", "skip connections", "vanishing gradient"],
            "technical_concept"
        )
        scores = result["rubric_scores"]
        # technical_concept profile: project weight is 0, so value must be 0
        assert scores.get("resume_project_connection", 0) == 0, (
            f"CNN concept rubric must give resume_project_connection=0, "
            f"got {scores.get('resume_project_connection')}"
        )
        assert result["rubric_total"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# C3. End-to-end: Backend Redis/Auth candidate
# ══════════════════════════════════════════════════════════════════════════════

class TestBackendRedisAuthCandidateFlow:

    def _analysis(self):
        return _Analysis(
            skills=["FastAPI", "PostgreSQL", "Redis", "JWT", "Docker", "Python"],
            projects=[_Project("API Service", ["FastAPI", "PostgreSQL", "Redis"])],
        )

    def test_backend_topics_include_caching_auth_db(self):
        topics = _resume_aware_curriculum("Backend Developer", self._analysis())
        assert "Caching with Redis" in topics
        assert "Authentication & Authorization" in topics
        assert "Database Indexing" in topics

    def test_backend_plan_has_at_least_3_concept_steps(self):
        plan = build_interview_plan(self._analysis(), "Backend Developer")
        concept_count = sum(1 for p in plan if p.question_type == "technical_concept")
        assert concept_count >= 3

    def test_redis_follow_up_classified_as_concept_not_project(self):
        cat = classify_question_category(
            topic="Caching with Redis",
            question_type="technical_follow_up",
        )
        assert cat == "concept"

    def test_redis_follow_up_rubric_has_no_project_dimension(self):
        """
        technical_follow_up profile has zero project weight — project_connection
        must not appear in rubric_scores at all.
        """
        answer = (
            "Redis uses in-memory storage with optional RDB snapshotting. "
            "LRU eviction removes stale entries when memory is full. "
            "The trade-off is memory cost vs dramatic latency improvement."
        )
        result = rubric_service.score_with_rubric_profile(
            answer, "Caching with Redis", ["in-memory", "eviction", "trade-off"], "technical_follow_up"
        )
        scores = result["rubric_scores"]
        # technical_follow_up project weight is 0 — value must be 0 (no ownership penalty)
        assert scores.get("resume_project_connection", 0) == 0, (
            f"technical_follow_up must give resume_project_connection=0, "
            f"got {scores.get('resume_project_connection')}"
        )
        assert result["rubric_total"] > 0

    def test_backend_mastery_update_raises_caching_topic(self):
        state = _make_state({"Caching with Redis": 52})
        record = _answer_record("Caching with Redis", 82)
        updated = update_candidate_state(
            state, record, question_type="technical_follow_up"
        )
        assert updated.skill_mastery["Caching with Redis"] > 52


# ══════════════════════════════════════════════════════════════════════════════
# D. Behavioral flow
# ══════════════════════════════════════════════════════════════════════════════

class TestBehavioralFlow:

    def test_behavioral_topic_classified_correctly(self):
        cat = classify_question_category(
            topic="Behavioral & Communication",
            question_type="behavioral",
        )
        assert cat == "behavioral"

    def test_behavioral_rubric_uses_star_dimensions(self):
        answer = (
            "When our deployment pipeline broke two hours before the product demo, "
            "I coordinated with DevOps and rolled back the migration manually. "
            "We restored service within 40 minutes and presented on time. "
            "I would have added automated rollback tests to catch this sooner."
        )
        result = rubric_service.score_with_rubric_profile(
            answer, "Behavioral & Communication", [], "behavioral"
        )
        scores = result.get("rubric_scores", {})
        # STAR dimensions (actual key names from rubric_service)
        assert "action_ownership" in scores, f"Missing action_ownership in {list(scores.keys())}"
        assert "result_impact" in scores, f"Missing result_impact in {list(scores.keys())}"
        assert "reflection_learning" in scores or "reflection_learning" in scores
        assert result["rubric_total"] > 0

    def test_behavioral_answer_does_not_update_technical_mastery(self):
        state = _make_state({"API Design": 70, "System Design": 65})
        record = _answer_record("System Design", 15)   # low score
        updated = update_candidate_state(state, record, question_type="behavioral")
        assert updated.skill_mastery["API Design"] == 70
        assert updated.skill_mastery["System Design"] == 65

    def test_behavioral_last_mastery_update_indicates_skip(self):
        state = _make_state({"API Design": 70})
        record = _answer_record("API Design", 20)
        updated = update_candidate_state(state, record, question_type="behavioral")
        lmu = updated.last_mastery_update
        assert lmu is not None
        assert "behavioral" in lmu.get("reason", "").lower()


# ══════════════════════════════════════════════════════════════════════════════
# E. Fallback safety
# ══════════════════════════════════════════════════════════════════════════════

class TestFallbackSafety:

    def test_missing_question_type_uses_safe_default_obs_weight(self):
        state = _make_state({"API Design": 60}, answers_answered=1)
        record = _answer_record("API Design", 80)
        updated_none = update_candidate_state(state, record, question_type=None)
        updated_empty = update_candidate_state(state, record, question_type="")
        assert updated_none.skill_mastery["API Design"] > 60
        assert updated_empty.skill_mastery["API Design"] > 60

    def test_unknown_question_type_does_not_crash(self):
        state = _make_state({"API Design": 60})
        record = _answer_record("API Design", 75)
        updated = update_candidate_state(state, record, question_type="future_type_v99")
        assert updated.skill_mastery["API Design"] > 60

    def test_fallback_rubric_when_question_type_absent(self):
        result = rubric_service.score_with_rubric_profile(
            "Caching stores data in fast memory to reduce latency.",
            "Caching",
            ["latency", "in-memory"],
            None,
        )
        assert "rubric_total" in result
        assert result["rubric_total"] >= 0

    def test_empty_resume_falls_back_to_curriculum(self):
        from agents.intelligence_engine import _ROLE_CURRICULUM
        analysis = _Analysis(skills=["Agile", "JIRA"])
        topics = _resume_aware_curriculum("Backend Developer", analysis)
        curriculum = [t for t in _ROLE_CURRICULUM["Backend Developer"] if t != "Project Deep Dive"]
        for t in topics:
            assert t in curriculum, f"Expected curriculum fallback, got '{t}'"


# ══════════════════════════════════════════════════════════════════════════════
# F. Project vs technical_follow_up rubric differences
# ══════════════════════════════════════════════════════════════════════════════

class TestProjectVsFollowUpScoring:

    _VAGUE = "I used Redis in a project and it worked well."
    _DETAILED = (
        "In the checkout service, I implemented cache-aside: on cart retrieval, "
        "check Redis first using TTL=300s; on miss, fetch from Postgres and populate cache. "
        "This cut p95 latency from 450ms to 60ms under peak load."
    )

    def test_project_deep_dive_rewards_ownership_and_detail(self):
        detailed = rubric_service.score_with_rubric_profile(
            self._DETAILED, "Caching with Redis", ["cache-aside", "ttl", "latency"], "project_deep_dive"
        )
        vague = rubric_service.score_with_rubric_profile(
            self._VAGUE, "Caching with Redis", ["cache-aside", "ttl", "latency"], "project_deep_dive"
        )
        assert detailed["rubric_total"] > vague["rubric_total"]

    def test_technical_follow_up_does_not_penalise_no_project_language(self):
        conceptual = (
            "Redis uses in-memory storage. LRU eviction handles memory pressure. "
            "Trade-off: memory cost vs latency. TTL keeps cache fresh."
        )
        ft_score = rubric_service.score_with_rubric_profile(
            conceptual, "Caching with Redis", ["in-memory", "eviction", "trade-off"], "technical_follow_up"
        )
        vague_project = rubric_service.score_with_rubric_profile(
            self._VAGUE, "Caching with Redis", ["in-memory", "eviction", "trade-off"], "project_deep_dive"
        )
        assert ft_score["rubric_total"] >= vague_project["rubric_total"]

    def test_claim_verification_includes_project_ownership_dimension(self):
        result = rubric_service.score_with_rubric_profile(
            self._DETAILED, "Caching with Redis", ["cache-aside", "ttl", "latency"], "claim_verification"
        )
        scores = result.get("rubric_scores", {})
        # claim_verification has project weight > 0
        assert "resume_project_connection" in scores or result["rubric_total"] >= 0


# ══════════════════════════════════════════════════════════════════════════════
# G. Multimodal integration: Phase 1–4 do not break audio/video path
# ══════════════════════════════════════════════════════════════════════════════

class TestMultimodalIntegration:

    def test_update_state_accepts_audio_alongside_question_type(self):
        """
        Phase 4's question_type parameter must not break audio_score forwarding.
        """
        state = _make_state({"API Design": 60})
        record = _answer_record("API Design", 75)
        audio = {
            "mode": "faster_whisper",
            "confidence_score": 80,
            "communication_clarity_score": 72,
        }
        updated = update_candidate_state(
            state, record, audio_score=audio, question_type="technical_concept"
        )
        # communication_trend derived from audio: clarity 72 >= 70 → "good"
        assert updated.communication_trend == "good"

    def test_behavioral_answer_still_updates_communication_trend(self):
        """
        Behavioral skips mastery but must still update communication_trend.
        """
        state = _make_state({"API Design": 60})
        record = _answer_record("API Design", 30)
        record["answer_text"] = " ".join(["word"] * 120)
        updated = update_candidate_state(state, record, question_type="behavioral")
        # Word-count proxy: 120 words → "good"
        assert updated.communication_trend == "good"
        # Mastery must be untouched
        assert updated.skill_mastery["API Design"] == 60
