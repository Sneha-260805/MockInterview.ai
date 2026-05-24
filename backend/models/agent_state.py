"""
Phase 11 — Agent State Models

Pydantic models representing the intelligence layer:
  - SkillSignal      : evidence of a skill from the resume
  - InterviewPlanItem: one step in the personalised interview plan
  - CandidateState   : evolving model of the candidate updated after every answer
  - AgentDecisionTrace: the reasoning behind each next-question decision
  - InterviewPlanResponse: API wrapper for the interview plan
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class SkillSignal(BaseModel):
    skill: str
    evidence_from_resume: List[str]
    confidence: int          # 0-100  how confident the agent is this skill exists
    source: str              # "resume_strength" | "project" | "skill_list" | "weak_area"


class InterviewPlanItem(BaseModel):
    step: int
    topic: str
    difficulty: str          # easy | medium | hard
    reason: str              # why this topic at this step
    linked_resume_evidence: List[str]   # concrete resume items that justify this step
    target_skill: str        # the underlying skill being probed


class CandidateState(BaseModel):
    session_id: str
    candidate_id: str
    selected_role: str
    inferred_level: str      # junior | mid | senior
    strong_skills: List[str]
    weak_skills: List[str]
    skill_mastery: Dict[str, int]       # topic → 0-100 live estimate
    confidence_trend: str               # improving | declining | stable | unknown
    communication_trend: str            # good | fair | poor | unknown
    risk_flags: List[str]               # e.g. "Weak on Database Design (2x)"
    last_decision: str                  # last decision_type applied
    next_best_action: str               # suggested next topic to probe
    answers_answered: int = Field(default=0)            # total answers processed so far
    concept_gaps: Dict[str, int] = Field(default_factory=dict)   # concept → miss count
    domain_performance: Dict[str, List[int]] = Field(default_factory=dict)  # topic → [scores]


class AgentDecisionTrace(BaseModel):
    decision_type: str       # increase_difficulty | deeper_follow_up |
                             # strengthen_fundamentals | confidence_recovery |
                             # remediation | final_synthesis | switch_topic |
                             # verify_resume_claim | behavioral_probe
    previous_topic: str
    previous_score: int
    detected_issue: str      # plain-English summary of what triggered this decision
    next_topic: str
    next_difficulty: str
    reason_for_adaptation: str          # human-readable explanation shown in UI
    evidence: List[str] = Field(default_factory=list)
    # Judge-ready / frontend fields (optional — backward compatible)
    observation: str = ""               # what the agent observed about the last answer
    signal_scores: Dict[str, Any] = Field(default_factory=dict)  # values may be null when unavailable
    difficulty_rationale: str = ""
    topic_rationale: str = ""
    next_question_strategy: str = ""    # e.g. same_topic_depth_probe, advance_uncovered_topic
    generation_mode: str = ""           # followup_generator | question_generator | fallback | pending
    generated_question_reason: str = "" # why this exact question was selected/generated
    followup_of_previous: Optional[bool] = None
    confidence_available: bool = False
    communication_available: bool = False
    engagement_available: bool = False
    confidence_note: str = ""           # explains unavailable or proxy signals


class InterviewPlanResponse(BaseModel):
    session_id: str
    selected_role: str
    inferred_level: str
    interview_plan: List[InterviewPlanItem]
    agent_summary: str       # 1-2 sentence plain English plan overview
