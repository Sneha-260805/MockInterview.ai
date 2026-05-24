"""
Primary-path follow-up routing for /next-question.

When the intelligence engine decides a follow-up is needed, try followup_generator
before falling back to question_generator. Orchestrator fallback is unchanged.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from models.agent_state import AgentDecisionTrace
from models.analysis import ResumeAnalysis
from models.interview import Question
from services import followup_generator, question_generator
from services.trace_enrichment import enrich_trace_after_question

logger = logging.getLogger(__name__)

_FOLLOWUP_DECISION_TYPES = frozenset({
    "deeper_follow_up",
    "ask_deeper_followup",
    "verify_resume_claim",
    "claim_verification",
})

_CONDITIONAL_FOLLOWUP_TYPES = frozenset({
    "strengthen_fundamentals",
    "remediation",
})

_SAME_TOPIC_STRATEGIES = frozenset({
    "same_topic_depth_probe",
    "remediation_weakest_or_gap_topic",
    "verify_resume_claim",
    "increase_difficulty_same_topic",
})


def _qid() -> str:
    return "Q" + str(uuid.uuid4()).replace("-", "")[:8].upper()


def _normalize_topic(topic: str) -> str:
    if topic.startswith("Follow-Up:"):
        return topic.split(":", 1)[1].strip()
    return topic.strip()


def _question_type_for_decision(decision_type: str) -> str:
    mapping = {
        "verify_resume_claim": "claim_verification",
        "claim_verification": "claim_verification",
        "deeper_follow_up": "follow_up",
        "ask_deeper_followup": "follow_up",
        "remediation": "fundamentals",
        "strengthen_fundamentals": "fundamentals",
    }
    return mapping.get(decision_type, "follow_up")


def should_try_followup(
    trace: AgentDecisionTrace,
    current_topic: str,
    missing_concepts: list[str],
) -> bool:
    """Return True when the primary path should attempt followup_generator."""
    if trace.decision_type in _FOLLOWUP_DECISION_TYPES:
        return True

    if trace.decision_type in _CONDITIONAL_FOLLOWUP_TYPES:
        normalized_current = _normalize_topic(current_topic)
        normalized_next = _normalize_topic(trace.next_topic)
        same_topic = (
            normalized_next == normalized_current
            or normalized_current in normalized_next
            or normalized_next in normalized_current
        )
        has_gaps = bool(missing_concepts)
        same_strategy = (
            trace.next_question_strategy in _SAME_TOPIC_STRATEGIES
            or same_topic
        )
        return has_gaps and same_topic

    return False


def try_build_followup_question(
    trace: AgentDecisionTrace,
    *,
    answer: str,
    current_topic: str,
    resume_techs: list[str],
    missing_concepts: list[str],
    covered_concepts: list[str],
    previous_question: str,
    difficulty: str,
    selected_role: str = "",
) -> tuple[Optional[Question], Optional[str]]:
    """
    Attempt to build a follow-up Question from followup_generator.

    Returns (question, trace_evidence) or (None, None).
    """
    if not should_try_followup(trace, current_topic, missing_concepts):
        return None, None

    try:
        result = followup_generator.generate_followup(
            answer=answer,
            current_topic=current_topic,
            resume_techs=resume_techs,
            missing_concepts=missing_concepts,
            covered_concepts=covered_concepts,
            previous_question=previous_question,
            selected_role=selected_role,
            decision_type=trace.decision_type,
            decision_reason=trace.reason_for_adaptation,
        )
        if not result:
            return None, None

        question_text, fu_reason, points = result
        if not question_text or len(question_text.strip()) < 20:
            return None, None

        base_topic = _normalize_topic(current_topic) or trace.next_topic
        topic_label = f"Follow-Up: {base_topic}"
        qtype = _question_type_for_decision(trace.decision_type)

        question = Question(
            question_id=_qid(),
            question=question_text,
            difficulty=difficulty,
            topic=topic_label,
            expected_points=points,
            expected_concepts=points,
            target_skill=base_topic,
            follow_up_intent=fu_reason,
            generation_mode="followup_generator",
            question_type=qtype,
            why_selected=fu_reason,
            followup_of_previous=True,
        )
        evidence = (
            f"Follow-up generated from candidate answer: {fu_reason} "
            f"The agent stayed on '{base_topic}' to probe implementation depth."
        )
        return question, evidence

    except Exception as exc:
        logger.warning("Primary follow-up generation failed: %s", exc)
        return None, None


def enrich_trace_with_followup(
    trace: AgentDecisionTrace,
    followup_evidence: str,
) -> AgentDecisionTrace:
    """Append follow-up evidence to the decision trace."""
    evidence = list(trace.evidence)
    if followup_evidence not in evidence:
        evidence.append(followup_evidence)
    return trace.model_copy(update={"evidence": evidence})


async def resolve_primary_next_question(
    trace: AgentDecisionTrace,
    *,
    role: str,
    analysis: ResumeAnalysis | None,
    last_answer_text: str,
    last_eval: dict,
    current_q_dict: dict,
    body_current_topic: str,
    turn_multi: dict,
    resume_techs: list[str],
) -> tuple[Question, AgentDecisionTrace]:
    """
    Primary-path next question resolution with follow-up precedence:

      a. followup_generator (when decision warrants it and output is useful)
      b. question_generator (LLM / deterministic with decision context)
    """
    current_topic = current_q_dict.get("topic", body_current_topic)
    missing = last_eval.get("missing_points", [])
    covered = last_eval.get("covered_points", [])

    followup_q, followup_evidence = try_build_followup_question(
        trace,
        answer=last_answer_text,
        current_topic=current_topic,
        resume_techs=resume_techs,
        missing_concepts=missing,
        covered_concepts=covered,
        previous_question=current_q_dict.get("question", ""),
        difficulty=trace.next_difficulty or "medium",
        selected_role=role,
    )

    if followup_q is not None:
        updated_trace = enrich_trace_with_followup(trace, followup_evidence) if followup_evidence else trace
        updated_trace = enrich_trace_after_question(
            updated_trace,
            followup_q,
            generation_mode="followup_generator",
            generated_question_reason=followup_q.why_selected or followup_evidence or "",
            answer_text=last_answer_text,
        )
        return followup_q, updated_trace

    generated = await question_generator.generate_question(
        role=role,
        topic=trace.next_topic or body_current_topic,
        difficulty=trace.next_difficulty or "medium",
        analysis=analysis,
        previous_answer=last_answer_text,
        previous_missing=missing,
        decision_type=trace.decision_type,
        decision_reason=trace.reason_for_adaptation,
        decision_trace=trace,
        missing_concepts=missing,
        covered_concepts=covered,
        current_topic=current_topic,
        previous_question=current_q_dict.get("question", ""),
        confidence_score=turn_multi.get("confidence_score"),
        communication_score=turn_multi.get("communication_score"),
        engagement_score=turn_multi.get("engagement_score"),
        follow_up_intent=trace.detected_issue,
        stay_on_topic=(
            trace.decision_type in ("deeper_follow_up", "verify_resume_claim", "claim_verification")
            or (
                trace.decision_type == "increase_difficulty"
                and trace.next_topic == current_topic
            )
            or (
                trace.decision_type in ("remediation", "strengthen_fundamentals")
                and trace.next_topic == _normalize_topic(current_topic)
            )
        ),
    )
    gen_reason = (
        generated.why_selected
        or generated.follow_up_intent
        or (
            f"Question shaped by agent decision '{trace.decision_type}' "
            f"for topic '{trace.next_topic}' at {trace.next_difficulty} difficulty."
        )
    )
    updated_trace = enrich_trace_after_question(
        trace,
        generated,
        generation_mode="question_generator",
        generated_question_reason=gen_reason,
        answer_text=last_answer_text,
    )
    return generated, updated_trace
