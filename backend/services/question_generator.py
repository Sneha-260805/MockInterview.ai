"""Resume-aware dynamic interview question generation.

The service prefers an LLM when configured, but the deterministic fallback is
still dynamic: it uses resume skills, projects, weak areas, target role/topic,
difficulty, and prior answer gaps.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from models.agent_state import AgentDecisionTrace
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


@dataclass
class QuestionDecisionContext:
    """Optional agent decision context passed from the intelligence engine."""

    decision_type: str = ""
    decision_reason: str = ""
    decision_trace: Optional[AgentDecisionTrace] = None
    missing_concepts: list[str] = field(default_factory=list)
    covered_concepts: list[str] = field(default_factory=list)
    current_topic: str = ""
    previous_question: str = ""
    previous_answer: str = ""
    confidence_score: Optional[int] = None
    communication_score: Optional[int] = None
    engagement_score: Optional[int] = None
    follow_up_intent: str = ""
    stay_on_topic: bool = False


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


def _resolve_topic(topic: str, ctx: QuestionDecisionContext) -> str:
    """When the agent says stay on topic, generate against the current topic."""
    if ctx.stay_on_topic or ctx.decision_type == "deeper_follow_up":
        return ctx.current_topic or topic
    return topic


def _resolve_stay_on_topic(
    decision_type: str,
    stay_on_topic: Optional[bool],
) -> bool:
    if stay_on_topic is not None:
        return stay_on_topic
    return decision_type == "deeper_follow_up"


def _build_decision_context(
    *,
    decision_type: str = "",
    decision_reason: str = "",
    decision_trace: Optional[AgentDecisionTrace] = None,
    missing_concepts: Optional[list[str]] = None,
    covered_concepts: Optional[list[str]] = None,
    missing_points: Optional[list[str]] = None,
    covered_points: Optional[list[str]] = None,
    current_topic: str = "",
    previous_question: str = "",
    previous_answer: str = "",
    confidence_score: Optional[int] = None,
    communication_score: Optional[int] = None,
    engagement_score: Optional[int] = None,
    follow_up_intent: str = "",
    stay_on_topic: Optional[bool] = None,
) -> QuestionDecisionContext:
    missing = missing_concepts or missing_points or []
    covered = covered_concepts or covered_points or []
    dtype = decision_type or (decision_trace.decision_type if decision_trace else "")
    reason = decision_reason or (
        decision_trace.reason_for_adaptation if decision_trace else ""
    )
    intent = follow_up_intent or (
        decision_trace.detected_issue if decision_trace else ""
    )
    return QuestionDecisionContext(
        decision_type=dtype,
        decision_reason=reason,
        decision_trace=decision_trace,
        missing_concepts=missing,
        covered_concepts=covered,
        current_topic=current_topic,
        previous_question=previous_question,
        previous_answer=previous_answer,
        confidence_score=confidence_score,
        communication_score=communication_score,
        engagement_score=engagement_score,
        follow_up_intent=intent,
        stay_on_topic=_resolve_stay_on_topic(dtype, stay_on_topic),
    )


def _decision_generation_rules(decision_type: str) -> str:
    rules = {
        "deeper_follow_up": (
            "STAY on the current topic. Ask a deeper follow-up that probes gaps "
            "from the previous answer. Reference what the candidate already said."
        ),
        "remediation": (
            "Ask a simpler fundamentals question targeting the missing concepts. "
            "Focus on core understanding before advancing."
        ),
        "strengthen_fundamentals": (
            "Ask a foundational question on the missing concepts. "
            "Use clear, structured wording and avoid trick questions."
        ),
        "confidence_recovery": (
            "Use supportive, encouraging wording. Keep difficulty easy or medium. "
            "Ask a structured question the candidate can answer confidently."
        ),
        "increase_difficulty": (
            "Generate a harder question that stretches the candidate. "
            "Include system-level or trade-off depth appropriate to the role."
        ),
        "switch_topic": (
            "Move to the assigned target topic — an important uncovered area. "
            "Do not repeat the previous question."
        ),
        "domain_pivot": (
            "Pivot to the assigned target topic at medium difficulty. "
            "Assess breadth across a different domain."
        ),
        "final_synthesis": (
            "Ask a synthesis question connecting multiple areas of the candidate's experience."
        ),
        "behavioral_probe": (
            "Generate a behavioral question connected to the role or resume. "
            "Use STAR-style framing about teamwork, debugging, or learning."
        ),
    }
    return rules.get(
        decision_type,
        "Generate an adaptive question aligned with the target topic and difficulty.",
    )


def build_llm_prompt(
    role: str,
    topic: str,
    difficulty: str,
    analysis: ResumeAnalysis | None,
    ctx: QuestionDecisionContext,
) -> str:
    """Build the LLM prompt including agent decision context (also used in tests)."""
    resume_ctx = _resume_context(analysis)
    effective_topic = _resolve_topic(topic, ctx)
    decision_rules = _decision_generation_rules(ctx.decision_type)

    signal_lines: list[str] = []
    if ctx.confidence_score is not None:
        signal_lines.append(f"Confidence score: {ctx.confidence_score}/100")
    if ctx.communication_score is not None:
        signal_lines.append(f"Communication clarity: {ctx.communication_score}/100")
    if ctx.engagement_score is not None:
        signal_lines.append(f"Engagement score: {ctx.engagement_score}/100")
    signals_block = "\n".join(signal_lines) if signal_lines else "Not available."

    trace_block = ""
    if ctx.decision_trace:
        trace = ctx.decision_trace
        trace_block = (
            f"Agent trace — previous topic: {trace.previous_topic}; "
            f"previous score: {trace.previous_score}/100; "
            f"detected issue: {trace.detected_issue}; "
            f"evidence: {json.dumps(trace.evidence[:4])}\n"
        )

    return (
        "You are an adaptive technical interviewer generating the NEXT question.\n\n"
        f"Role: {role}\n"
        f"Target topic: {effective_topic}\n"
        f"Target difficulty: {difficulty}\n"
        f"Resume context: {json.dumps(resume_ctx)}\n\n"
        "── Agent decision ──\n"
        f"decision_type: {ctx.decision_type or 'standard_advance'}\n"
        f"reason_for_adaptation: {ctx.decision_reason or 'Continue the interview plan.'}\n"
        f"follow_up_intent: {ctx.follow_up_intent or 'Probe role-relevant depth.'}\n"
        f"stay_on_topic: {ctx.stay_on_topic}\n"
        f"{trace_block}"
        f"Generation rule: {decision_rules}\n\n"
        "── Previous turn ──\n"
        f"Current topic: {ctx.current_topic or effective_topic}\n"
        f"Previous question: {ctx.previous_question[:400]}\n"
        f"Previous answer excerpt: {ctx.previous_answer[:500]}\n"
        f"Missing concepts: {json.dumps(ctx.missing_concepts[:6])}\n"
        f"Covered concepts: {json.dumps(ctx.covered_concepts[:6])}\n\n"
        "── Candidate signals ──\n"
        f"{signals_block}\n\n"
        "Return ONLY valid JSON (no markdown, no prose):\n"
        "{\n"
        '  "question": "...",\n'
        '  "topic": "...",\n'
        '  "difficulty": "easy|medium|hard",\n'
        '  "question_type": "technical|behavioral|follow_up|fundamentals|synthesis",\n'
        '  "expected_concepts": ["...", "..."],\n'
        '  "expected_points": ["...", "..."],\n'
        '  "why_selected": "one sentence explaining why this question matches the agent decision",\n'
        '  "followup_of_previous": true|false,\n'
        '  "follow_up_intent": "...",\n'
        '  "target_skill": "..."\n'
        "}"
    )


def _question_from_llm_data(
    data: dict,
    topic: str,
    difficulty: str,
    ctx: QuestionDecisionContext,
    effective_topic: str,
) -> Question:
    concepts = data.get("expected_concepts") or data.get("expected_points") or _concepts(effective_topic)
    resolved_topic = data.get("topic") or effective_topic
    resolved_diff = data.get("difficulty") or difficulty
    why = data.get("why_selected") or ctx.decision_reason or ctx.follow_up_intent
    followup = data.get("followup_of_previous")
    if followup is None:
        followup = ctx.stay_on_topic or ctx.decision_type == "deeper_follow_up"

    return Question(
        question_id=_qid(),
        question=data["question"],
        difficulty=resolved_diff,
        topic=resolved_topic,
        expected_points=data.get("expected_points", concepts),
        target_skill=data.get("target_skill", resolved_topic),
        evaluation_rubric=_rubric(resolved_topic, concepts),
        expected_concepts=concepts,
        follow_up_intent=data.get("follow_up_intent") or ctx.follow_up_intent or "LLM-generated adaptive probe.",
        generation_mode="llm",
        question_type=data.get("question_type"),
        why_selected=why,
        followup_of_previous=bool(followup),
    )


def _fallback_question(
    role: str,
    topic: str,
    difficulty: str,
    analysis: ResumeAnalysis | None,
    ctx: QuestionDecisionContext,
) -> Question:
    effective_topic = _resolve_topic(topic, ctx)
    previous_missing = ctx.missing_concepts
    previous_answer = ctx.previous_answer
    resume_ctx = _resume_context(analysis)
    skills = resume_ctx["skills"]
    weak = resume_ctx["weak"]
    projects = resume_ctx["projects"]
    skill = skills[0] if skills else effective_topic
    concepts = _concepts(effective_topic, skill)
    missing = previous_missing or []

    project_name = projects[0]["name"] if projects else "one of your projects"
    project_tech = ", ".join(projects[0].get("technologies", [])[:3]) if projects else ", ".join(skills[:3])
    weak_hint = weak[0] if weak else (missing[0] if missing else concepts[0])

    dtype = ctx.decision_type
    why = ctx.decision_reason or "Resume-aware adaptive question."
    followup = ctx.stay_on_topic or dtype == "deeper_follow_up"
    qtype = "technical"

    if dtype == "behavioral_probe":
        # Pick a project-connected question when resume data is available,
        # otherwise fall back to a role-generic behavioral prompt.
        if projects:
            text = (
                f"Tell me about a time you faced a significant challenge or setback while "
                f"building your {project_name} project. How did you handle it, what trade-offs "
                "did you make, and what did you learn from the experience?"
            )
        elif skills:
            text = (
                f"Describe a situation where you had to make a difficult trade-off between "
                f"speed and quality while working with {', '.join(skills[:2])}. "
                "Walk me through your decision and the outcome."
            )
        else:
            text = (
                f"Tell me about a time you had to take ownership of a difficult problem "
                f"outside your immediate scope as a {role}. "
                "What steps did you take and what was the result?"
            )
        concepts = [
            "Describes the situation and challenge clearly",
            "Explains decision-making and communication approach",
            "Shows ownership and accountability",
            "Reflects on lessons learned or outcome",
        ]
        intent = f"Behavioral probe to assess ownership, communication, and reflection for {role}."
        why = ctx.decision_reason or f"Behavioral validation after technical assessment for {role}."
        qtype = "behavioral"
        effective_topic = "Behavioral & Communication"
        skill = "Behavioral & Communication"
    elif dtype in ("remediation", "strengthen_fundamentals") and missing:
        gap = missing[0]
        text = (
            f"Let's step back to fundamentals on {effective_topic}. "
            f"Can you explain {gap} in plain terms and give a simple example from your experience?"
        )
        intent = f"Fundamentals remediation targeting missing concept: {gap}."
        qtype = "fundamentals"
        why = ctx.decision_reason or f"Remediation probe for gap: {gap}."
    elif dtype == "confidence_recovery":
        text = (
            f"No worries — let's try a structured question. "
            f"In your own words, how would you describe the core idea behind {effective_topic} "
            f"for a {role} role? A concrete example from {project_name} would be great."
        )
        intent = "Supportive confidence-recovery question with clear structure."
        qtype = "technical"
        difficulty = "easy" if difficulty != "easy" else difficulty
    elif dtype == "deeper_follow_up":
        gap_text = f" Specifically, expand on {', '.join(missing[:2])}." if missing else ""
        text = (
            f"Good start on {ctx.current_topic or effective_topic}. "
            f"Going deeper — what trade-offs did you consider, and what would you do differently?{gap_text}"
        )
        intent = ctx.follow_up_intent or "Deeper follow-up on the same topic."
        qtype = "follow_up"
        followup = True
    elif dtype == "increase_difficulty":
        text = (
            f"Design a production-grade solution involving {effective_topic} for a {role}. "
            f"Use your background in {', '.join(skills[:3]) or skill}, cover {', '.join(concepts[:3])}, "
            "and explain bottlenecks, failure modes, and observability."
        )
        intent = "Increased difficulty to test ceiling knowledge."
        difficulty = "hard" if difficulty != "hard" else difficulty
    elif effective_topic == "Project Deep Dive" and projects:
        text = (
            f"Walk me through {project_name}. For a {role} interview, explain the architecture, "
            f"why you chose {project_tech or 'the main technologies'}, the hardest trade-off, "
            f"and how you would improve it now."
        )
        intent = "Validate resume project ownership and technical trade-off reasoning."
        skill = "Technical Communication"
    elif difficulty == "hard":
        text = (
            f"Design a production-grade solution involving {effective_topic} for a {role}. "
            f"Use your background in {', '.join(skills[:3]) or skill}, cover {', '.join(concepts[:3])}, "
            "and explain bottlenecks, failure modes, and observability."
        )
        intent = "Stretch system-level reasoning and seniority."
        skill = effective_topic
    elif difficulty == "medium":
        prior = " Your previous answer left gaps around " + ", ".join(missing[:2]) + "." if missing else ""
        text = (
            f"Given your resume mentions {', '.join(skills[:4]) or skill}, how would you apply {effective_topic} "
            f"in a real {role} project?{prior} Include the main steps, trade-offs, and how you would test it."
        )
        intent = "Probe practical depth and close prior gaps."
        skill = effective_topic
    else:
        text = (
            f"Let's establish fundamentals: explain {effective_topic} for a {role} role using a concrete example "
            f"from {project_name if projects else 'your experience'}. Be sure to cover {', '.join(concepts[:3])}."
        )
        if weak_hint:
            text += f" I also want to understand your comfort with {weak_hint}."
        intent = "Check fundamentals with resume grounding."
        skill = effective_topic

    return Question(
        question_id=_qid(),
        question=text,
        difficulty=difficulty,
        topic=effective_topic,
        expected_points=concepts,
        target_skill=skill if isinstance(skill, str) else effective_topic,
        evaluation_rubric=_rubric(effective_topic, concepts),
        expected_concepts=concepts,
        follow_up_intent=intent,
        generation_mode="deterministic_dynamic",
        question_type=qtype,
        why_selected=why,
        followup_of_previous=followup,
    )


async def _llm_question(
    role: str,
    topic: str,
    difficulty: str,
    analysis: ResumeAnalysis | None,
    ctx: QuestionDecisionContext,
) -> Question | None:
    from config import get_settings
    settings = get_settings()
    if not settings.has_llm_configured:
        return None
    try:
        from services.llm_client import call_llm

        effective_topic = _resolve_topic(topic, ctx)
        prompt = build_llm_prompt(role, topic, difficulty, analysis, ctx)
        raw = await call_llm(prompt, max_tokens=700)
        if not raw:
            return None
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        if not data.get("question", "").strip():
            return None
        return _question_from_llm_data(data, topic, difficulty, ctx, effective_topic)
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
    *,
    decision_type: str = "",
    decision_reason: str = "",
    decision_trace: Optional[AgentDecisionTrace] = None,
    missing_concepts: Optional[list[str]] = None,
    covered_concepts: Optional[list[str]] = None,
    covered_points: Optional[list[str]] = None,
    current_topic: str = "",
    previous_question: str = "",
    confidence_score: Optional[int] = None,
    communication_score: Optional[int] = None,
    engagement_score: Optional[int] = None,
    follow_up_intent: str = "",
    stay_on_topic: Optional[bool] = None,
) -> Question:
    ctx = _build_decision_context(
        decision_type=decision_type,
        decision_reason=decision_reason,
        decision_trace=decision_trace,
        missing_concepts=missing_concepts,
        covered_concepts=covered_concepts,
        missing_points=previous_missing,
        covered_points=covered_points,
        current_topic=current_topic,
        previous_question=previous_question,
        previous_answer=previous_answer,
        confidence_score=confidence_score,
        communication_score=communication_score,
        engagement_score=engagement_score,
        follow_up_intent=follow_up_intent,
        stay_on_topic=stay_on_topic,
    )
    llm_q = await _llm_question(role, topic, difficulty, analysis, ctx)
    if llm_q:
        return llm_q
    return _fallback_question(role, topic, difficulty, analysis, ctx)
