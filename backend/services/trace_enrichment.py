"""Enrich AgentDecisionTrace after question generation for judge-ready responses."""

from __future__ import annotations

import re

from models.agent_state import AgentDecisionTrace
from models.interview import Question


def build_followup_observation(
    trace: AgentDecisionTrace,
    answer_text: str,
    question: Question,
) -> str:
    """Observation text when a follow-up question was generated."""
    al = answer_text.lower()
    topic = trace.previous_topic or "the previous topic"
    missing_evidence = next(
        (e for e in trace.evidence if e.lower().startswith("missing:")),
        "",
    )
    missing_part = missing_evidence.replace("Missing:", "").strip() if missing_evidence else ""

    if "redis" in al:
        return (
            "Candidate mentioned Redis performance improvement, but did not explain "
            "cache invalidation or TTL."
        )
    if re.search(r"\bauth(?:entication)?\b|\blogin\b", al):
        return (
            f"Candidate referenced authentication on '{topic}' at a high level "
            "without explaining method choice or route/API protection."
        )
    if re.search(r"\bbackend apis?\b|\bbuilt apis?\b", al):
        return (
            "Candidate claimed backend API work but did not walk through validation, "
            "error handling, or database interaction."
        )
    if missing_part:
        return (
            f"Candidate gave a partial answer on '{topic}' and missed {missing_part}."
        )
    intent = question.why_selected or question.follow_up_intent or trace.detected_issue
    return (
        f"Candidate's answer on '{topic}' warrants a targeted follow-up: {intent}"
    )


def enrich_trace_after_question(
    trace: AgentDecisionTrace,
    question: Question,
    *,
    generation_mode: str,
    generated_question_reason: str = "",
    answer_text: str = "",
) -> AgentDecisionTrace:
    """Attach generation metadata and optional follow-up observation to the trace."""
    reason = generated_question_reason or question.why_selected or question.follow_up_intent or ""
    observation = trace.observation

    if generation_mode == "followup_generator" and answer_text:
        observation = build_followup_observation(trace, answer_text, question)

    evidence = list(trace.evidence)
    action_line = f"Action taken: generated next question via {generation_mode}."
    if action_line not in evidence:
        evidence.append(action_line)
    if reason:
        gen_line = f"Generated question reason: {reason[:160]}"
        if gen_line not in evidence:
            evidence.append(gen_line)

    return trace.model_copy(
        update={
            "observation": observation,
            "generation_mode": generation_mode,
            "generated_question_reason": reason,
            "followup_of_previous": question.followup_of_previous,
            "evidence": evidence,
        }
    )


def build_fallback_trace(
    *,
    previous_topic: str,
    previous_score: int,
    next_topic: str,
    next_difficulty: str,
    reason: str,
) -> AgentDecisionTrace:
    """Minimal trace when the orchestrator fallback path is used."""
    return AgentDecisionTrace(
        decision_type="fallback",
        previous_topic=previous_topic,
        previous_score=previous_score,
        detected_issue="Intelligence engine path unavailable; safe orchestrator fallback used.",
        next_topic=next_topic,
        next_difficulty=next_difficulty,
        reason_for_adaptation=reason,
        observation=(
            f"Primary agent path could not produce the next question; "
            f"fallback orchestrator selected '{next_topic}'."
        ),
        evidence=[
            f"Technical score on prior answer: {previous_score}/100",
            "Action taken: generated next question via fallback orchestrator.",
        ],
        generation_mode="fallback",
        generated_question_reason=reason,
        topic_rationale="Fallback orchestrator selected the next question from its static/LLM bank.",
        difficulty_rationale="Fallback orchestrator applied its built-in difficulty rules.",
        next_question_strategy="orchestrator_fallback",
    )
