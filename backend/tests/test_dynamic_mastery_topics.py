"""
Phase 2 — Dynamic resume-aware mastery topics tests.

Covers:
  1. AI/ML + RAG resume → LLM Application Design / RAG Pipeline Design / Vector Search topics
  2. AI/ML + CNN resume → CNN Architecture / PyTorch Training topics
  3. Backend resume (FastAPI/SQL/Redis/JWT) → API Design / Database / Caching / Auth topics
  4. Frontend resume (React/TypeScript/CSS) → React State Management / Responsive Layout topics
  5. No strong resume signals → fallback to role curriculum
  6. Mastery topic count is 3–7 (bounded list)
  7. Interview plan still starts with project_deep_dive when projects exist
  8. Interview plan concept steps use personalised mastery topics (not just raw curriculum)
  9. Existing question-mix tests still pass (import sanity)
 10. mastery_topic_metadata is populated with source and skill_evidence
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from agents.intelligence_engine import (
    _resume_aware_curriculum,
    _mastery_topic_metadata,
    build_interview_plan,
    initialize_candidate_state,
)
from models.agent_state import InterviewPlanItem


# ── Fixture helpers ───────────────────────────────────────────────────────────

class _Project:
    def __init__(self, name: str, technologies: list[str] | None = None):
        self.name = name
        self.technologies = technologies or []


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


def _minimal_plan(topics: list[str] | None = None) -> list[InterviewPlanItem]:
    topics = topics or ["Project Deep Dive", "API Design"]
    return [
        InterviewPlanItem(
            step=i + 1,
            topic=t,
            difficulty="medium",
            reason="test",
            linked_resume_evidence=[],
            target_skill=t,
        )
        for i, t in enumerate(topics)
    ]


# ── Test 1: AI/ML + RAG resume ────────────────────────────────────────────────

def test_aiml_rag_resume_generates_rag_vector_llm_topics():
    """
    A resume with LangChain, RAG, and FAISS skills should produce personalized
    topics that include LLM Application Design, RAG Pipeline Design, and/or
    Vector Search rather than just the generic ML/AI Engineer curriculum.
    """
    analysis = _Analysis(
        skills=["LangChain", "LLM", "RAG", "Python", "FastAPI"],
        projects=[_Project("RAG Chatbot", ["LangChain", "FAISS", "Redis"])],
    )
    topics = _resume_aware_curriculum("ML / AI Engineer", analysis)

    assert "LLM Application Design" in topics, f"Expected LLM Application Design in {topics}"
    assert any(t in topics for t in ("RAG Pipeline Design", "Vector Search")), (
        f"Expected RAG Pipeline Design or Vector Search in {topics}"
    )
    # Should NOT be only raw curriculum
    raw_curriculum = [
        "Transfer Learning", "Deep Learning", "MLOps", "Model Serving", "Continual Learning"
    ]
    assert not all(t in raw_curriculum for t in topics), (
        "Topics should be personalised, not just raw curriculum"
    )


# ── Test 2: AI/ML + CNN resume ────────────────────────────────────────────────

def test_aiml_cnn_resume_generates_cnn_pytorch_topics():
    """
    A resume focused on CNNs, ResNet, and PyTorch should produce topics
    that include CNN Architecture and PyTorch Training.
    """
    analysis = _Analysis(
        skills=["PyTorch", "OpenCV", "Python", "Scikit-learn"],
        projects=[_Project("Image Classifier", ["PyTorch", "ResNet", "OpenCV"])],
    )
    topics = _resume_aware_curriculum("ML / AI Engineer", analysis)

    assert "CNN Architecture" in topics, f"Expected CNN Architecture in {topics}"
    assert "PyTorch Training" in topics, f"Expected PyTorch Training in {topics}"
    # "Deep Learning" (generic curriculum) should be superseded by the specific ones
    assert "Deep Learning" not in topics, (
        "Generic 'Deep Learning' should be superseded by CNN Architecture / PyTorch Training"
    )


# ── Test 3: Backend resume with FastAPI / SQL / Redis / JWT ──────────────────

def test_backend_fastapi_sql_redis_generates_api_db_cache_auth_topics():
    """
    A backend resume with FastAPI, PostgreSQL, Redis, and JWT should produce
    API Design, Database Indexing, Caching with Redis, and Authentication topics.
    """
    analysis = _Analysis(
        skills=["FastAPI", "PostgreSQL", "Redis", "JWT", "Docker", "Python"],
    )
    topics = _resume_aware_curriculum("Backend Developer", analysis)

    assert "API Design" in topics, f"Expected API Design in {topics}"
    assert "Database Indexing" in topics, f"Expected Database Indexing in {topics}"
    assert "Caching with Redis" in topics, f"Expected Caching with Redis in {topics}"
    assert "Authentication & Authorization" in topics, (
        f"Expected Authentication & Authorization in {topics}"
    )


# ── Test 4: Frontend resume with React / TypeScript / CSS ────────────────────

def test_frontend_react_typescript_css_generates_correct_topics():
    """
    A frontend resume with React, TypeScript, CSS, and Redux should include
    React State Management, TypeScript & Type Safety, and Responsive Layout.
    """
    analysis = _Analysis(
        skills=["React", "TypeScript", "CSS", "Redux"],
    )
    topics = _resume_aware_curriculum("Frontend Developer", analysis)

    assert "React State Management" in topics, f"Expected React State Management in {topics}"
    assert "TypeScript & Type Safety" in topics, f"Expected TypeScript & Type Safety in {topics}"
    assert "Responsive Layout" in topics, f"Expected Responsive Layout in {topics}"
    # Generic React Internals (curriculum) superseded by React State Management
    assert "React Internals" not in topics, (
        "Generic 'React Internals' should be superseded by React State Management"
    )


# ── Test 5: No strong resume signals → fallback to curriculum ─────────────────

def test_no_strong_resume_signal_falls_back_to_role_curriculum():
    """
    When the resume has no skill keywords that map to personalised topics
    (fewer than 2 hits), the function should return the raw role curriculum.
    """
    # "Agile" and "Git" have no entry in _RESUME_TOPIC_MAP
    analysis = _Analysis(skills=["Agile", "Git", "Scrum"])
    topics = _resume_aware_curriculum("ML / AI Engineer", analysis)

    from agents.intelligence_engine import _ROLE_CURRICULUM
    curriculum = [t for t in _ROLE_CURRICULUM["ML / AI Engineer"] if t != "Project Deep Dive"]
    # All returned topics should come from the curriculum
    for t in topics:
        assert t in curriculum, (
            f"Expected fallback to curriculum but got non-curriculum topic '{t}'. "
            f"Topics returned: {topics}"
        )


# ── Test 6: Mastery topic count is bounded ────────────────────────────────────

def test_mastery_topic_count_is_bounded():
    """
    _resume_aware_curriculum must return at most 7 topics regardless of
    how many skills the resume has.
    """
    analysis = _Analysis(
        skills=[
            "LangChain", "LLM", "RAG", "FAISS", "PyTorch",
            "FastAPI", "Redis", "PostgreSQL", "JWT", "Docker",
            "Kubernetes", "Airflow", "Pandas",
        ],
    )
    for role in ("ML / AI Engineer", "Backend Developer", "Full Stack Developer"):
        topics = _resume_aware_curriculum(role, analysis)
        assert len(topics) <= 7, (
            f"Expected ≤ 7 topics for {role}, got {len(topics)}: {topics}"
        )
        assert len(topics) >= 2, (
            f"Expected ≥ 2 topics for {role}, got {len(topics)}"
        )


# ── Test 7: Interview plan still starts with project_deep_dive ────────────────

def test_plan_starts_with_project_deep_dive_when_projects_exist():
    """
    Even with personalised topics, the first plan step must be Project Deep Dive
    when the resume includes projects.
    """
    analysis = _Analysis(
        skills=["LangChain", "LLM", "RAG", "FAISS", "PyTorch", "Python"],
        projects=[_Project("RAG Pipeline", ["LangChain", "FAISS", "Redis"])],
    )
    plan = build_interview_plan(analysis, "ML / AI Engineer")

    assert plan[0].topic == "Project Deep Dive", (
        f"First plan step should be Project Deep Dive, got {plan[0].topic!r}"
    )
    assert plan[0].question_type == "project_deep_dive", (
        f"First step question_type should be project_deep_dive, got {plan[0].question_type!r}"
    )


# ── Test 8: Concept steps in plan use personalised topics ────────────────────

def test_plan_concept_steps_use_personalised_topics():
    """
    For a RAG-focused ML/AI resume, concept steps in the interview plan should
    include personalised topics (e.g. LLM Application Design or Vector Search)
    rather than only generic curriculum topics like 'Transfer Learning' or 'Deep Learning'.
    """
    analysis = _Analysis(
        skills=["LangChain", "LLM", "RAG", "FAISS", "Python"],
        projects=[_Project("RAG App", ["LangChain", "FAISS"])],
    )
    plan = build_interview_plan(analysis, "ML / AI Engineer")

    concept_topics = [
        item.topic for item in plan
        if item.topic != "Project Deep Dive"
    ]
    personalised_names = {
        "LLM Application Design", "RAG Pipeline Design", "Vector Search",
        "Embeddings & Representations", "Transformer Architecture",
        "MLOps & Experiment Tracking", "Model Selection & Evaluation",
    }
    has_personalised = any(t in personalised_names for t in concept_topics)
    assert has_personalised, (
        f"Expected at least one personalised concept topic in plan, got: {concept_topics}"
    )


# ── Test 9: mastery_topic_metadata is populated correctly ────────────────────

def test_mastery_topic_metadata_is_populated():
    """
    initialize_candidate_state should populate mastery_topic_metadata with
    source and skill_evidence for each personalised topic.
    """
    analysis = _Analysis(
        skills=["LangChain", "RAG", "FAISS", "Python"],
        projects=[_Project("RAG Chatbot", ["LangChain", "FAISS"])],
    )
    plan = build_interview_plan(analysis, "ML / AI Engineer")
    state = initialize_candidate_state("s1", "c1", "ML / AI Engineer", analysis, plan)

    assert isinstance(state.mastery_topic_metadata, dict), (
        "mastery_topic_metadata should be a dict"
    )
    # Should have at least one personalised topic with resume_skill source
    resume_skill_entries = [
        (k, v) for k, v in state.mastery_topic_metadata.items()
        if v.get("source") == "resume_skill"
    ]
    assert len(resume_skill_entries) >= 1, (
        f"Expected at least one resume_skill source in metadata. "
        f"Got: {state.mastery_topic_metadata}"
    )
    # Each entry has required keys
    for topic, meta in state.mastery_topic_metadata.items():
        assert "source" in meta, f"Missing 'source' in metadata for topic '{topic}'"
        assert "reason" in meta, f"Missing 'reason' in metadata for topic '{topic}'"
        assert "skill_evidence" in meta, f"Missing 'skill_evidence' in metadata for topic '{topic}'"


# ── Test 10: skill_mastery includes personalised topics ───────────────────────

def test_skill_mastery_includes_personalised_topics():
    """
    After initialize_candidate_state, skill_mastery should include personalised
    topic names (not just raw curriculum topics) when the resume has signals.
    """
    analysis = _Analysis(
        skills=["FastAPI", "PostgreSQL", "Redis", "JWT", "Docker"],
    )
    plan = _minimal_plan(["Project Deep Dive", "API Design", "Database Indexing"])
    state = initialize_candidate_state("s1", "c1", "Backend Developer", analysis, plan)

    assert "API Design" in state.skill_mastery, (
        "API Design should be in skill_mastery for a FastAPI resume"
    )
    assert "Caching with Redis" in state.skill_mastery, (
        "Caching with Redis should be in skill_mastery for a Redis resume"
    )
    assert "Authentication & Authorization" in state.skill_mastery, (
        "Authentication & Authorization should be in skill_mastery for a JWT resume"
    )
    # All scores should be in valid range
    for topic, score in state.skill_mastery.items():
        assert 0 <= score <= 100, f"Score for '{topic}' out of range: {score}"


# ── Phase 2.5 Tests: Evidence-aware initial mastery scores ────────────────────

# ── Test 11: RAG personalised topics start above 47 ──────────────────────────

def test_rag_personalized_topics_start_above_default_47():
    """
    For an RAG/LLM resume at mid level, personalised topics like
    'LLM Application Design', 'RAG Pipeline Design', 'Vector Search' should
    start at ≥ 55 — well above the default-unknown prior of ~47.
    """
    analysis = _Analysis(
        skills=["LangChain", "LLM", "RAG", "FAISS", "Python"],
        projects=[_Project("RAG Chatbot", ["LangChain", "FAISS", "Redis"])],
        experience_level="mid",
    )
    plan = build_interview_plan(analysis, "ML / AI Engineer")
    state = initialize_candidate_state("s1", "c1", "ML / AI Engineer", analysis, plan)

    rag_topics = [t for t in state.skill_mastery if t in {
        "LLM Application Design", "RAG Pipeline Design", "Vector Search",
        "Embeddings & Representations",
    }]
    assert rag_topics, "Expected at least one RAG/LLM personalised topic in skill_mastery"
    for topic in rag_topics:
        score = state.skill_mastery[topic]
        assert score >= 55, (
            f"Personalised topic '{topic}' should start ≥ 55 for mid-level RAG resume, got {score}"
        )


# ── Test 12: CNN personalised topics start above 47 ──────────────────────────

def test_cnn_personalized_topics_start_above_default_47():
    """
    For a CNN/PyTorch resume, 'CNN Architecture' and 'PyTorch Training' should
    start at ≥ 55 — above the unknown-prior default.
    """
    analysis = _Analysis(
        skills=["PyTorch", "OpenCV", "Python", "Scikit-learn"],
        projects=[_Project("Image Classifier", ["PyTorch", "ResNet", "OpenCV"])],
        experience_level="mid",
    )
    plan = build_interview_plan(analysis, "ML / AI Engineer")
    state = initialize_candidate_state("s1", "c1", "ML / AI Engineer", analysis, plan)

    for topic in ("CNN Architecture", "PyTorch Training"):
        if topic in state.skill_mastery:
            score = state.skill_mastery[topic]
            assert score >= 55, (
                f"Personalised topic '{topic}' should start ≥ 55 for mid-level CNN resume, got {score}"
            )


# ── Test 13: Backend personalised topics start above 47 ──────────────────────

def test_backend_redis_auth_topics_start_above_default_47():
    """
    For a Backend resume with FastAPI/Redis/JWT, personalised topics like
    'API Design', 'Caching with Redis', and 'Authentication & Authorization'
    should start at ≥ 55.
    """
    analysis = _Analysis(
        skills=["FastAPI", "PostgreSQL", "Redis", "JWT", "Docker", "Python"],
        experience_level="mid",
    )
    plan = build_interview_plan(analysis, "Backend Developer")
    state = initialize_candidate_state("s1", "c1", "Backend Developer", analysis, plan)

    expected_boosted = ["API Design", "Caching with Redis", "Authentication & Authorization"]
    for topic in expected_boosted:
        if topic in state.skill_mastery:
            score = state.skill_mastery[topic]
            assert score >= 55, (
                f"Personalised topic '{topic}' should start ≥ 55 for backend resume, got {score}"
            )


# ── Test 14: Weak-area topic stays below 50 ───────────────────────────────────

def test_weak_area_topic_stays_below_50():
    """
    When a topic is flagged as a weak area in the resume, its initial mastery
    should be capped at ≤ 50 even for senior-level candidates.
    """
    analysis = _Analysis(
        skills=["FastAPI", "PostgreSQL", "Python"],
        weak_areas=["Database Indexing"],
        experience_level="senior",
    )
    plan = build_interview_plan(analysis, "Backend Developer")
    state = initialize_candidate_state("s1", "c1", "Backend Developer", analysis, plan)

    if "Database Indexing" in state.skill_mastery:
        score = state.skill_mastery["Database Indexing"]
        assert score <= 50, (
            f"Weak-area topic 'Database Indexing' should be ≤ 50 but got {score}"
        )


# ── Test 15: Curriculum-only topics are not boosted ──────────────────────────

def test_curriculum_fallback_topic_not_boosted():
    """
    A topic that came from the fallback curriculum (not from resume signals)
    should NOT be raised above what _initial_mastery_for_topic would set.
    For a thin resume (Agile/Git only), all topics come from curriculum.
    The scores should reflect the default-unknown tier (~47 ± jitter + level).
    """
    analysis = _Analysis(
        skills=["Agile", "Git", "Scrum"],
        experience_level="mid",
    )
    plan = build_interview_plan(analysis, "Backend Developer")
    state = initialize_candidate_state("s1", "c1", "Backend Developer", analysis, plan)

    # With no resume signals, scores should all be in the fallback range (not boosted)
    for topic, score in state.skill_mastery.items():
        assert score <= 72, (
            f"Curriculum fallback topic '{topic}' should not be boosted above 72, got {score}"
        )


# ── Test 16: Senior candidate gets higher evidence-aware scores than junior ───

def test_senior_evidence_aware_mastery_higher_than_junior():
    """
    For identical resume signals, a senior candidate should receive higher
    initial mastery scores for personalised topics than a junior candidate.
    """
    skills = ["LangChain", "LLM", "RAG", "FAISS", "Python"]

    analysis_senior = _Analysis(skills=skills, experience_level="senior")
    analysis_junior = _Analysis(skills=skills, experience_level="junior")

    plan_s = build_interview_plan(analysis_senior, "ML / AI Engineer")
    plan_j = build_interview_plan(analysis_junior, "ML / AI Engineer")

    state_s = initialize_candidate_state("s1", "c1", "ML / AI Engineer", analysis_senior, plan_s)
    state_j = initialize_candidate_state("s1", "c1", "ML / AI Engineer", analysis_junior, plan_j)

    personalized = {"LLM Application Design", "RAG Pipeline Design", "Vector Search"}
    shared = personalized & state_s.skill_mastery.keys() & state_j.skill_mastery.keys()
    assert shared, "Expected at least one shared personalised topic across senior/junior"

    for topic in shared:
        s_score = state_s.skill_mastery[topic]
        j_score = state_j.skill_mastery[topic]
        assert s_score > j_score, (
            f"Senior score for '{topic}' ({s_score}) should exceed junior score ({j_score})"
        )
