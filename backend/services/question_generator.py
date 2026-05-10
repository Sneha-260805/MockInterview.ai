"""Resume-aware dynamic interview question generation.

The service prefers an LLM when configured, but the deterministic fallback is
still dynamic: it uses resume skills, projects, weak areas, target role/topic,
difficulty, and prior answer gaps.
"""

import json
import logging
import re
import uuid
from typing import Any

from models.analysis import ResumeAnalysis
from models.interview import Question

logger = logging.getLogger(__name__)


def _qid() -> str:
    return "Q" + str(uuid.uuid4()).replace("-", "")[:8].upper()


_TOPIC_CONCEPTS: dict[str, list[str]] = {
    "Project Deep Dive": ["architecture", "trade-offs", "implementation details", "measurable impact"],
    "REST Fundamentals": ["statelessness", "HTTP verbs", "status codes", "resource modelling"],
    "API Design": ["idempotency", "versioning", "validation", "error handling"],
    "Database Design": ["schema design", "indexes", "transactions", "query patterns"],
    "Database": ["transactions", "isolation levels", "indexes", "query optimization"],
    "Authentication": ["token flow", "refresh strategy", "secure storage", "authorization"],
    "System Design": ["scalability", "availability", "data model", "bottlenecks"],
    "Performance Optimization": ["profiling", "caching", "latency", "load testing"],
    "React Internals": ["rendering", "state", "hooks", "memoization"],
    "Frontend Architecture": ["state management", "component boundaries", "accessibility", "performance"],
    "MLOps": ["model registry", "deployment", "monitoring", "drift"],
    "Model Selection": ["baseline", "metrics", "bias-variance", "interpretability"],
}


def _concepts(topic: str, fallback_skill: str = "") -> list[str]:
    return _TOPIC_CONCEPTS.get(topic, [fallback_skill or topic, "trade-offs", "failure modes", "real example"])


def _rubric(topic: str, concepts: list[str]) -> dict[str, Any]:
    return {
        "conceptual_correctness": 30,
        "practical_application": 25,
        "depth_and_tradeoffs": 20,
        "communication_structure": 15,
        "resume_project_connection": 10,
        "expected_concepts": concepts,
        "topic": topic,
    }


def _resume_context(analysis: ResumeAnalysis | None) -> dict[str, Any]:
    if not analysis:
        return {"skills": [], "weak": [], "projects": []}
    return {
        "skills": analysis.skills[:10],
        "weak": analysis.weak_areas[:4],
        "projects": [p.model_dump() for p in analysis.projects[:3]],
        "level": analysis.experience_level,
        "domains": analysis.domains[:3],
    }


def _fallback_question(
    role: str,
    topic: str,
    difficulty: str,
    analysis: ResumeAnalysis | None,
    previous_answer: str = "",
    previous_missing: list[str] | None = None,
) -> Question:
    ctx = _resume_context(analysis)
    skills = ctx["skills"]
    weak = ctx["weak"]
    projects = ctx["projects"]
    skill = skills[0] if skills else topic
    concepts = _concepts(topic, skill)
    missing = previous_missing or []

    project_name = projects[0]["name"] if projects else "one of your projects"
    project_tech = ", ".join(projects[0].get("technologies", [])[:3]) if projects else ", ".join(skills[:3])
    weak_hint = weak[0] if weak else (missing[0] if missing else concepts[0])

    if topic == "Project Deep Dive" and projects:
        text = (
            f"Walk me through {project_name}. For a {role} interview, explain the architecture, "
            f"why you chose {project_tech or 'the main technologies'}, the hardest trade-off, "
            f"and how you would improve it now."
        )
        intent = "Validate resume project ownership and technical trade-off reasoning."
        target_skill = "Technical Communication"
    elif difficulty == "hard":
        text = (
            f"Design a production-grade solution involving {topic} for a {role}. "
            f"Use your background in {', '.join(skills[:3]) or skill}, cover {', '.join(concepts[:3])}, "
            "and explain bottlenecks, failure modes, and observability."
        )
        intent = "Stretch system-level reasoning and seniority."
        target_skill = topic
    elif difficulty == "medium":
        prior = " Your previous answer left gaps around " + ", ".join(missing[:2]) + "." if missing else ""
        text = (
            f"Given your resume mentions {', '.join(skills[:4]) or skill}, how would you apply {topic} "
            f"in a real {role} project?{prior} Include the main steps, trade-offs, and how you would test it."
        )
        intent = "Probe practical depth and close prior gaps."
        target_skill = topic
    else:
        text = (
            f"Let's establish fundamentals: explain {topic} for a {role} role using a concrete example "
            f"from {project_name if projects else 'your experience'}. Be sure to cover {', '.join(concepts[:3])}."
        )
        if weak_hint:
            text += f" I also want to understand your comfort with {weak_hint}."
        intent = "Check fundamentals with resume grounding."
        target_skill = topic

    return Question(
        question_id=_qid(),
        question=text,
        difficulty=difficulty,
        topic=topic,
        expected_points=concepts,
        target_skill=target_skill,
        evaluation_rubric=_rubric(topic, concepts),
        expected_concepts=concepts,
        follow_up_intent=intent,
        generation_mode="deterministic_dynamic",
    )


async def _llm_question(
    role: str,
    topic: str,
    difficulty: str,
    analysis: ResumeAnalysis | None,
    previous_answer: str,
    previous_missing: list[str],
) -> Question | None:
    from config import get_settings
    settings = get_settings()
    if not settings.has_llm_configured:
        return None
    try:
        from services.llm_client import call_llm
        ctx = _resume_context(analysis)
        prompt = (
            "Generate one resume-aware technical interview question as JSON only.\n"
            f"Role: {role}\nTopic: {topic}\nDifficulty: {difficulty}\n"
            f"Resume context: {json.dumps(ctx)}\n"
            f"Previous answer excerpt: {previous_answer[:500]}\n"
            f"Missing concepts from previous answer: {previous_missing[:4]}\n"
            'Return: {"question":"...","expected_points":["..."],"target_skill":"...",'
            '"expected_concepts":["..."],"follow_up_intent":"..."}'
        )
        raw = await call_llm(prompt, max_tokens=700)
        if not raw:
            return None
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        concepts = data.get("expected_concepts") or data.get("expected_points") or _concepts(topic)
        return Question(
            question_id=_qid(),
            question=data["question"],
            difficulty=difficulty,
            topic=topic,
            expected_points=data.get("expected_points", concepts),
            target_skill=data.get("target_skill", topic),
            evaluation_rubric=_rubric(topic, concepts),
            expected_concepts=concepts,
            follow_up_intent=data.get("follow_up_intent", "LLM-generated adaptive probe."),
            generation_mode="llm",
        )
    except Exception as exc:
        logger.warning("LLM question generation failed: %s", exc)
        return None


async def generate_question(
    role: str,
    topic: str,
    difficulty: str,
    analysis: ResumeAnalysis | None = None,
    previous_answer: str = "",
    previous_missing: list[str] | None = None,
) -> Question:
    previous_missing = previous_missing or []
    llm_q = await _llm_question(role, topic, difficulty, analysis, previous_answer, previous_missing)
    if llm_q:
        return llm_q
    return _fallback_question(role, topic, difficulty, analysis, previous_answer, previous_missing)
