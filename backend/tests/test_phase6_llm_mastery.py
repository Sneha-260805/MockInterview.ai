"""
Phase 6 — Generic Resume-Agnostic Mastery Topic Generation tests.

Verifies that synthesize_mastery_topics_with_llm():
  - Synthesises role-appropriate topics for 6 non-standard roles (Cloud, DevOps,
    Data Engineer, Cybersecurity, QA Automation, Embedded) when LLM is available.
  - Returns None on bad JSON, 1-topic response, or LLM unavailable.
  - Trims >7 topics to 7 and deduplicates near-identical names.
  - Downstream: initialize_candidate_state uses llm_topics for mastery init
    and records generation_mode in mastery_topic_metadata.
  - Downstream: build_interview_plan uses llm_topics for concept steps.
  - All deterministic paths (llm_topics=None) continue to work.

Baseline: 306 passed, 2 skipped (pre-Phase-6).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agents.intelligence_engine import (
    _validate_and_sanitize_llm_topics,
    _similar_topic,
    _mastery_from_llm_confidence,
    synthesize_mastery_topics_with_llm,
    build_interview_plan,
    initialize_candidate_state,
)
from models.agent_state import InterviewPlanItem


# ── Shared helpers ─────────────────────────────────────────────────────────────

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


class _Settings:
    has_llm_configured = True
    llm_provider = "gemini"


def _llm_json(topics: list[dict]) -> str:
    return json.dumps({"topics": topics})


def _topic_entry(
    name: str,
    source: str = "role_expectation",
    confidence: float = 0.65,
    evidence: list[str] | None = None,
    angles: list[str] | None = None,
) -> dict:
    return {
        "topic": name,
        "source": source,
        "evidence": evidence or [],
        "reason": f"{name} is important for the role.",
        "initial_confidence": confidence,
        "question_angles": angles or ["concepts", "trade-offs"],
    }


def _make_plan(role: str, analysis) -> list[InterviewPlanItem]:
    return build_interview_plan(analysis, role)


# ── Test 1: Cloud Engineer synthesis ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_cloud_engineer_synthesis(monkeypatch):
    """LLM synthesises ≥5 topics for a Cloud Engineer candidate."""
    analysis = _Analysis(
        skills=["AWS", "Terraform", "Kubernetes", "CI/CD", "Python"],
        projects=[_Project("Infra Automation", ["Terraform", "AWS Lambda"])],
        domains=["Cloud"],
    )
    raw_topics = [
        _topic_entry("Cloud Infrastructure", "resume_skill", 0.80, ["AWS"]),
        _topic_entry("Infrastructure as Code", "resume_skill", 0.75, ["Terraform"]),
        _topic_entry("Container Orchestration", "resume_skill", 0.70, ["Kubernetes"]),
        _topic_entry("CI/CD Pipelines", "resume_skill", 0.65),
        _topic_entry("Observability & Monitoring", "role_expectation", 0.50),
    ]

    async def _mock_llm(prompt, max_tokens=1200):
        return _llm_json(raw_topics)

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("Cloud Engineer", analysis)

    assert result is not None
    assert len(result) >= 5
    topic_names = [t["topic"] for t in result]
    assert "Cloud Infrastructure" in topic_names
    assert "Infrastructure as Code" in topic_names
    for t in result:
        assert "topic" in t and "source" in t and "initial_confidence" in t


# ── Test 2: DevOps synthesis ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_devops_synthesis(monkeypatch):
    """LLM synthesises ≥5 topics for a DevOps engineer candidate."""
    analysis = _Analysis(
        skills=["Docker", "Kubernetes", "Jenkins", "Ansible", "Shell"],
        projects=[_Project("Pipeline Automation", ["Jenkins", "Docker"])],
    )
    raw_topics = [
        _topic_entry("CI/CD Design", "resume_project", 0.78, ["Jenkins"]),
        _topic_entry("Container Management", "resume_skill", 0.72, ["Docker", "Kubernetes"]),
        _topic_entry("Configuration Management", "resume_skill", 0.60, ["Ansible"]),
        _topic_entry("Security Hardening", "role_expectation", 0.45),
        _topic_entry("Site Reliability", "role_expectation", 0.50),
    ]

    async def _mock_llm(prompt, max_tokens=1200):
        return _llm_json(raw_topics)

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("DevOps Engineer", analysis)

    assert result is not None
    assert len(result) >= 5
    assert any(t["topic"] == "CI/CD Design" for t in result)


# ── Test 3: Data Engineer synthesis ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_data_engineer_synthesis(monkeypatch):
    """LLM synthesises ≥5 topics for a Data Engineer candidate."""
    analysis = _Analysis(
        skills=["Apache Spark", "Airflow", "SQL", "Kafka", "Python"],
        projects=[_Project("ETL Pipeline", ["Spark", "Airflow"])],
    )
    raw_topics = [
        _topic_entry("Distributed Processing", "resume_skill", 0.80, ["Apache Spark"]),
        _topic_entry("Pipeline Orchestration", "resume_skill", 0.75, ["Airflow"]),
        _topic_entry("Stream Processing", "resume_skill", 0.65, ["Kafka"]),
        _topic_entry("Data Modelling", "role_expectation", 0.55),
        _topic_entry("Data Quality", "role_expectation", 0.50),
    ]

    async def _mock_llm(prompt, max_tokens=1200):
        return _llm_json(raw_topics)

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("Data Engineer", analysis)

    assert result is not None
    assert len(result) >= 5
    assert any(t["topic"] == "Distributed Processing" for t in result)


# ── Test 4: Cybersecurity synthesis ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_cybersecurity_synthesis(monkeypatch):
    """LLM synthesises ≥5 topics for a Cybersecurity candidate."""
    analysis = _Analysis(
        skills=["Penetration Testing", "SIEM", "OWASP", "Python", "Wireshark"],
        weak_areas=["Cloud Security"],
    )
    raw_topics = [
        _topic_entry("Penetration Testing Methodology", "resume_skill", 0.80, ["Penetration Testing"]),
        _topic_entry("Threat Detection & SIEM", "resume_skill", 0.72, ["SIEM"]),
        _topic_entry("OWASP Vulnerabilities", "resume_skill", 0.70, ["OWASP"]),
        _topic_entry("Network Analysis", "resume_skill", 0.65, ["Wireshark"]),
        _topic_entry("Cloud Security", "weak_area", 0.35, [], ["controls", "IAM"]),
    ]

    async def _mock_llm(prompt, max_tokens=1200):
        return _llm_json(raw_topics)

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("Cybersecurity Engineer", analysis)

    assert result is not None
    assert len(result) >= 5
    # weak_area confidence capped at 0.4 → mastery score ≤ ~50
    cloud_sec = next((t for t in result if t["topic"] == "Cloud Security"), None)
    assert cloud_sec is not None
    assert cloud_sec["source"] == "weak_area"
    assert cloud_sec["initial_confidence"] <= 0.4


# ── Test 5: QA Automation synthesis ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_qa_automation_synthesis(monkeypatch):
    """LLM synthesises ≥5 topics for a QA Automation candidate."""
    analysis = _Analysis(
        skills=["Selenium", "Pytest", "Postman", "BDD", "CI/CD"],
    )
    raw_topics = [
        _topic_entry("Test Automation Frameworks", "resume_skill", 0.78, ["Selenium", "Pytest"]),
        _topic_entry("API Testing", "resume_skill", 0.72, ["Postman"]),
        _topic_entry("Behaviour Driven Development", "resume_skill", 0.65, ["BDD"]),
        _topic_entry("CI/CD Integration", "resume_skill", 0.60, ["CI/CD"]),
        _topic_entry("Performance Testing", "role_expectation", 0.45),
    ]

    async def _mock_llm(prompt, max_tokens=1200):
        return _llm_json(raw_topics)

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("QA Automation Engineer", analysis)

    assert result is not None
    assert len(result) >= 5
    assert any(t["topic"] == "Test Automation Frameworks" for t in result)


# ── Test 6: Embedded synthesis ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_embedded_synthesis(monkeypatch):
    """LLM synthesises ≥5 topics for an Embedded Systems candidate."""
    analysis = _Analysis(
        skills=["C", "C++", "RTOS", "ARM Cortex", "UART/SPI/I2C"],
    )
    raw_topics = [
        _topic_entry("RTOS Concepts", "resume_skill", 0.78, ["RTOS"]),
        _topic_entry("Memory Management", "role_expectation", 0.60),
        _topic_entry("Hardware Protocols", "resume_skill", 0.70, ["UART/SPI/I2C"]),
        _topic_entry("ARM Architecture", "resume_skill", 0.65, ["ARM Cortex"]),
        _topic_entry("Interrupt Handling", "role_expectation", 0.50),
    ]

    async def _mock_llm(prompt, max_tokens=1200):
        return _llm_json(raw_topics)

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("Embedded Systems Engineer", analysis)

    assert result is not None
    assert len(result) >= 5
    assert any(t["topic"] == "RTOS Concepts" for t in result)


# ── Test 7: Bad LLM JSON → deterministic fallback (None) ─────────────────────

@pytest.mark.asyncio
async def test_bad_llm_json_returns_none(monkeypatch):
    """When LLM returns unparseable text, synthesize returns None."""
    analysis = _Analysis(skills=["Python"])

    async def _mock_llm(prompt, max_tokens=1200):
        return "Here are some topics: 1) Algorithms 2) Data Structures"  # no JSON

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("Cloud Engineer", analysis)

    assert result is None, "Expected None when LLM returns non-JSON text"


# ── Test 8: LLM returns 10 topics → trimmed to 7 ─────────────────────────────

@pytest.mark.asyncio
async def test_ten_topics_trimmed_to_seven(monkeypatch):
    """_validate_and_sanitize trims more than 7 topics down to 7."""
    raw_topics = [
        _topic_entry(f"Topic {i}", "role_expectation", 0.60)
        for i in range(1, 11)   # 10 unique topics
    ]

    analysis = _Analysis(skills=["Python"])

    async def _mock_llm(prompt, max_tokens=1200):
        return _llm_json(raw_topics)

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("Cloud Engineer", analysis)

    assert result is not None
    assert len(result) <= 7, f"Expected ≤7 topics, got {len(result)}"


# ── Test 9: Duplicate/near-duplicate topics → deduplicated ───────────────────

@pytest.mark.asyncio
async def test_duplicate_topics_deduplicated(monkeypatch):
    """Near-duplicate topic names are collapsed to one entry."""
    raw_topics = [
        _topic_entry("Cloud Infrastructure", "role_expectation", 0.70),
        _topic_entry("Cloud Infrastructure Design", "role_expectation", 0.65),  # near-dupe
        _topic_entry("Cloud Infrastructure Management", "role_expectation", 0.60),  # near-dupe
        _topic_entry("Container Orchestration", "resume_skill", 0.72),
        _topic_entry("CI/CD Pipelines", "resume_skill", 0.68),
        _topic_entry("Observability", "role_expectation", 0.55),
    ]

    analysis = _Analysis(skills=["AWS", "Kubernetes"])

    async def _mock_llm(prompt, max_tokens=1200):
        return _llm_json(raw_topics)

    monkeypatch.setattr("config.get_settings", lambda: _Settings())
    monkeypatch.setattr("services.llm_client.call_llm", _mock_llm)

    result = await synthesize_mastery_topics_with_llm("Cloud Engineer", analysis)

    assert result is not None
    # The three "Cloud Infrastructure*" variants should reduce to 1
    cloud_infra_count = sum(
        1 for t in result
        if _similar_topic(t["topic"], "Cloud Infrastructure")
    )
    assert cloud_infra_count == 1, (
        f"Expected 1 cloud-infra entry after dedup, got {cloud_infra_count}: "
        f"{[t['topic'] for t in result]}"
    )


# ── Test 10: LLM unavailable → None ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_unavailable_returns_none(monkeypatch):
    """When has_llm_configured is False, synthesize returns None immediately."""
    class _NoLLM:
        has_llm_configured = False

    analysis = _Analysis(skills=["Python"])
    monkeypatch.setattr("config.get_settings", lambda: _NoLLM())

    result = await synthesize_mastery_topics_with_llm("Cloud Engineer", analysis)

    assert result is None


# ── Test 11: Deterministic path unbroken (llm_topics=None) ───────────────────

def test_deterministic_path_unchanged_for_existing_roles():
    """
    When llm_topics=None, initialize_candidate_state falls back to the Phase 2
    deterministic curriculum.  Tests the three roles from Phase 5 to confirm
    the baseline is unbroken.
    """
    for role, skills, project_name, project_techs in [
        ("ML / AI Engineer", ["Python", "PyTorch", "RAG", "LangChain"],
         "RAG Chatbot", ["LangChain", "FAISS", "OpenAI"]),
        ("ML / AI Engineer", ["PyTorch", "CNN", "Image Classification"],
         "CNN Classifier", ["PyTorch", "OpenCV"]),
        ("Backend Developer", ["Python", "Redis", "FastAPI", "JWT"],
         "Auth Service", ["FastAPI", "Redis"]),
    ]:
        analysis = _Analysis(
            skills=skills,
            projects=[_Project(project_name, project_techs)],
        )
        plan = build_interview_plan(analysis, role)
        state = initialize_candidate_state(
            session_id="det-session",
            candidate_id="det-cand",
            selected_role=role,
            resume_analysis=analysis,
            interview_plan=plan,
            llm_topics=None,
        )

        assert len(state.skill_mastery) >= 3, f"Expected ≥3 mastery topics for {role}"
        assert state.inferred_level in {"junior", "mid", "senior"}
        # Deterministic path metadata should tag each entry
        for topic, meta in state.mastery_topic_metadata.items():
            assert "generation_mode" in meta, (
                f"deterministic meta missing generation_mode for topic '{topic}'"
            )
            assert meta["generation_mode"] == "deterministic_fallback"


# ── Test 12: Plan uses LLM-generated topics for concept questions ─────────────

def test_plan_uses_llm_topics_for_concept_steps():
    """
    When llm_topics is provided, build_interview_plan uses those topics
    for step-3 curriculum slots (non-project-deep-dive).
    """
    analysis = _Analysis(
        skills=["Terraform", "Kubernetes"],
        projects=[_Project("Infra Automation", ["Terraform", "AWS"])],
    )
    llm_topics = [
        _topic_entry("Infrastructure as Code", "resume_skill", 0.78, ["Terraform"]),
        _topic_entry("Kubernetes Internals", "resume_skill", 0.72, ["Kubernetes"]),
        _topic_entry("Service Mesh", "role_expectation", 0.55),
        _topic_entry("Cloud Networking", "role_expectation", 0.50),
        _topic_entry("GitOps Workflow", "role_expectation", 0.48),
    ]

    plan = build_interview_plan(analysis, "Cloud Engineer", llm_topics=llm_topics)

    plan_topic_names = [item.topic for item in plan]
    # At least one LLM-generated concept topic should appear in the plan
    llm_names = {t["topic"] for t in llm_topics}
    overlap = llm_names & set(plan_topic_names)
    assert len(overlap) >= 1, (
        f"Expected ≥1 LLM topic in plan; plan={plan_topic_names}, llm={list(llm_names)}"
    )


# ── Test 13: mastery_topic_metadata includes generation_mode ─────────────────

def test_mastery_topic_metadata_includes_generation_mode_llm():
    """
    When llm_topics is passed to initialize_candidate_state, the
    mastery_topic_metadata entries for LLM-sourced topics must have
    generation_mode='llm' and include question_angles.
    """
    analysis = _Analysis(
        skills=["Docker", "Kubernetes"],
        projects=[_Project("K8s Infra", ["Kubernetes"])],
    )
    llm_topics = [
        {
            "topic": "Container Orchestration",
            "source": "resume_skill",
            "evidence": ["Kubernetes"],
            "reason": "Core skill shown in resume.",
            "initial_confidence": 0.75,
            "question_angles": ["scheduling", "networking", "scaling"],
        },
        {
            "topic": "Cloud Networking",
            "source": "role_expectation",
            "evidence": [],
            "reason": "Required for cloud-native deployments.",
            "initial_confidence": 0.50,
            "question_angles": ["VPC", "DNS"],
        },
        {
            "topic": "Security Best Practices",
            "source": "role_expectation",
            "evidence": [],
            "reason": "All cloud engineers must know security basics.",
            "initial_confidence": 0.48,
            "question_angles": ["RBAC", "secrets management"],
        },
        {
            "topic": "CI/CD Automation",
            "source": "role_expectation",
            "evidence": [],
            "reason": "Core DevOps skill.",
            "initial_confidence": 0.55,
            "question_angles": ["pipelines", "rollback"],
        },
        {
            "topic": "Observability",
            "source": "role_expectation",
            "evidence": [],
            "reason": "Needed for production reliability.",
            "initial_confidence": 0.50,
            "question_angles": ["metrics", "tracing"],
        },
    ]

    plan = build_interview_plan(analysis, "Cloud Engineer", llm_topics=llm_topics)
    state = initialize_candidate_state(
        session_id="gen-session",
        candidate_id="gen-cand",
        selected_role="Cloud Engineer",
        resume_analysis=analysis,
        interview_plan=plan,
        llm_topics=llm_topics,
    )

    meta = state.mastery_topic_metadata
    assert len(meta) > 0, "mastery_topic_metadata must be non-empty"

    # Every LLM topic's metadata entry must carry generation_mode
    for t in llm_topics:
        topic_name = t["topic"]
        if topic_name in meta:
            entry = meta[topic_name]
            assert "generation_mode" in entry, (
                f"generation_mode missing for LLM topic '{topic_name}'"
            )
            assert entry["generation_mode"] == "llm", (
                f"Expected 'llm' for topic '{topic_name}', got '{entry['generation_mode']}'"
            )
            assert "question_angles" in entry, (
                f"question_angles missing for LLM topic '{topic_name}'"
            )

    # Mastery scores for LLM topics should be in [10, 95]
    for t in llm_topics:
        topic_name = t["topic"]
        if topic_name in state.skill_mastery:
            score = state.skill_mastery[topic_name]
            assert 10 <= score <= 95, (
                f"skill_mastery['{topic_name}'] = {score} out of [10, 95]"
            )
