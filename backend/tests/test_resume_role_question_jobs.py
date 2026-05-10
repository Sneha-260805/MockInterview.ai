import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agents import resume_agent, role_agent, job_recommender_agent
from services import question_generator


def test_resume_extracts_extended_fields():
    text = """
    Sneha Rao
    Senior Backend Engineer
    Experience
    Led API platform migration for 5 years across payments and analytics.
    Projects
    Interview Agent
    Built with Python, FastAPI, React, PostgreSQL and Docker.
    Education
    B.Tech Computer Science
    Certifications
    AWS Solutions Architect
    Skills
    Python FastAPI React PostgreSQL Docker AWS
    """
    result = resume_agent.analyze(text, "cand-test")
    assert "Python" in result.skills
    assert result.projects
    assert result.experience
    assert result.seniority_signals
    assert result.domain_exposure
    assert result.certifications


def test_resume_extracts_project_when_pdf_puts_header_inline():
    text = """
    Sneha Rao
    SKILLS Python FastAPI React PostgreSQL
    PROJECTS Interview Agent
    Built a resume-aware mock interview platform using Python, FastAPI, React and Docker.
    Added adaptive scoring and feedback.
    EDUCATION B.Tech Computer Science
    """
    result = resume_agent.analyze(text, "cand-inline-project")
    assert result.projects
    assert result.projects[0].name == "Interview Agent"
    assert "FastAPI" in result.projects[0].technologies
    assert any("adaptive scoring" in line.lower() for line in result.projects[0].description)


def test_resume_keeps_bullet_only_project_section_together():
    text = """
    Sneha Rao
    Skills
    Python FastAPI Docker
    Projects
    - Built an interview agent with resume parsing, adaptive questions, and feedback.
    - Used FastAPI, Docker, and React for the demo workflow.
    Education
    B.Tech Computer Science
    """
    result = resume_agent.analyze(text, "cand-bullet-project")
    assert len(result.projects) == 1
    assert len(result.projects[0].description) >= 1


def test_resume_does_not_extract_git_repo_links_as_projects():
    text = """
    Sneha Rao
    Skills
    Python FastAPI React Docker
    Projects
    Interview Agent
    GitHub: https://github.com/sneha/interview-agent
    Built adaptive interview questions and multimodal feedback with FastAPI and React.
    Portfolio Site
    Repo: github.com/sneha/portfolio
    Designed a responsive React portfolio.
    Education
    B.Tech Computer Science
    """
    result = resume_agent.analyze(text, "cand-links")
    names = [project.name.lower() for project in result.projects]
    assert "interview agent" in names
    assert "portfolio site" in names
    assert not any("github" in name or "repo:" in name or "http" in name for name in names)
    assert any("github.com/sneha/interview-agent" in line for line in result.projects[0].description)


def test_role_inference_contains_evidence_and_focus():
    analysis = resume_agent.analyze(
        "Skills: Python FastAPI PostgreSQL Docker AWS React JavaScript\nProjects\nAPI Platform\nBuilt REST APIs.",
        "cand-role",
    )
    result = role_agent.recommend(analysis)
    first = result.recommended_roles[0]
    assert first.evidence
    assert first.confidence is not None
    assert first.interview_focus_areas


@pytest.mark.asyncio
async def test_dynamic_question_changes_with_resume_and_difficulty(monkeypatch):
    from config import get_settings
    monkeypatch.setenv("USE_LLM", "false")
    get_settings.cache_clear()
    backend = resume_agent.analyze(
        "Skills: Python FastAPI PostgreSQL\nProjects\nAPI Platform\nBuilt APIs.",
        "cand-q1",
    )
    frontend = resume_agent.analyze(
        "Skills: React TypeScript CSS\nProjects\nDesign System\nBuilt components.",
        "cand-q2",
    )
    q1 = await question_generator.generate_question("Backend Developer", "API Design", "easy", backend)
    q2 = await question_generator.generate_question("Frontend Developer", "Frontend Architecture", "hard", frontend)
    assert q1.question != q2.question
    assert q1.generation_mode == "deterministic_dynamic"
    assert q2.difficulty == "hard"
    assert q2.evaluation_rubric
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_job_recommendations_label_fallback_samples(monkeypatch):
    async def _none(*args, **kwargs):
        return []

    monkeypatch.setattr("agents.adzuna_job_fetcher.fetch_live_jobs", _none)
    result = await job_recommender_agent.recommend(
        "cand-job", ["Python", "React", "Docker"], "mid", "Candidate"
    )
    assert result.is_live is False
    assert result.fallback_reason
    assert result.recommended_jobs
    assert all(j.is_fallback_sample for j in result.recommended_jobs)
