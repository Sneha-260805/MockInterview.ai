from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class Question(BaseModel):
    question_id: str
    question: str
    difficulty: str        # easy | medium | hard
    topic: str
    expected_points: List[str]
    target_skill: Optional[str] = None
    evaluation_rubric: Optional[Dict[str, Any]] = None
    expected_concepts: Optional[List[str]] = None
    follow_up_intent: Optional[str] = None
    generation_mode: Optional[str] = None


class EvaluationResult(BaseModel):
    # ── Core scores (original — never removed) ────────────────────────────────
    technical_score: int
    depth_score: int
    correctness_score: int
    covered_points: List[str]
    missing_points: List[str]
    feedback: str
    evaluation_mode: str = "rule_based"          # "ai" | "rule_based"
    evaluation_provider: str = "rule_based"      # "gemini" | "anthropic" | "rule_based"
    evaluation_source_label: str = "Rule-based evaluation"
    # ── Phase 11: Rubric-based additions (optional — backward compatible) ──────
    rubric_scores: Optional[Dict[str, int]] = None   # dimension -> 0-30/25/20/15/10
    rubric_total: Optional[int] = None               # 0-100
    evidence: Optional[List[str]] = None             # matched concepts
    improvement_hint: Optional[str] = None           # targeted coaching tip
    interviewer_diagnosis: Optional[str] = None      # 1-sentence diagnosis


class AnswerRecord(BaseModel):
    question_id: str
    question: str
    answer_text: str
    evaluation: EvaluationResult
    answered_at: datetime
    attempt_number: int = 1


# ── Coaching loop models ──────────────────────────────────────────────────────

class ImproveAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    question: str
    improved_answer: str
    expected_points: List[str]
    previous_evaluation: Dict[str, Any]   # EvaluationResult as dict from first attempt
    attempt_number: int = 2               # 2 = first retry, 3 = second, etc.
    topic: Optional[str] = None


class ImprovedEvaluationResult(EvaluationResult):
    """EvaluationResult extended with improvement-comparison data."""
    attempt_number: int = 2
    previous_scores: Dict[str, int] = {}       # {"technical": 53, "depth": 40, "correctness": 59}
    improvement_delta: Dict[str, int] = {}     # {"technical": +21, "depth": +18, "correctness": +8}
    newly_covered: List[str] = []              # concepts covered now that were missing before
    still_missing: List[str] = []              # concepts still missing after retry


class InterviewSession(BaseModel):
    session_id: str
    candidate_id: str
    selected_role: str
    status: str            # active | completed
    created_at: datetime
    questions_asked: List[Question] = []
    current_question: Optional[Question] = None
    answers: List[AnswerRecord] = []
    adaptation_log: List[str] = []   # reason_for_adaptation for Q2, Q3, … in order
    audio_scores: List[dict] = []    # AudioAnalysisResponse dicts keyed by question_number
    video_scores: List[dict] = []    # VideoAnalysisResponse dicts keyed by question_number


class StartInterviewRequest(BaseModel):
    candidate_id: str
    selected_role: str


class StartInterviewResponse(BaseModel):
    session_id: str
    candidate_id: str
    selected_role: str
    first_question: Question
    # Phase 11 additions (optional — backward compatible)
    interview_plan: Optional[List[Any]] = None    # List[InterviewPlanItem] serialised
    agent_summary: Optional[str] = None
    candidate_state: Optional[Any] = None         # CandidateState serialised
    inferred_level: Optional[str] = None


class EvaluateAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    question: str
    answer: str
    expected_points: List[str]
    topic: Optional[str] = None   # Phase 11: for rubric selection


class NextQuestionRequest(BaseModel):
    session_id: str
    last_answer_score: int   # technical_score from last evaluation (0-100)
    confidence_score: int    # 0-100, derived by frontend from eval + answer length
    current_topic: str


class NextQuestionResponse(BaseModel):
    next_question: Question
    reason_for_adaptation: str
    session_complete: bool = False
    questions_answered: int = 0
    max_questions: int = 5
    # Phase 11 additions (optional — backward compatible)
    decision_trace: Optional[Any] = None          # AgentDecisionTrace serialised
    candidate_state: Optional[Any] = None         # updated CandidateState serialised


# ── Phase 6: Final Report models ──────────────────────────────────────────────

class AnswerSummary(BaseModel):
    question_number: int
    question: str
    topic: str
    difficulty: str
    technical_score: int
    depth_score: int
    correctness_score: int
    covered_points: List[str]
    missing_points: List[str]
    adaptation_reason: Optional[str] = None
    # Audio intelligence fields (populated when /api/scoring/audio was called)
    audio_transcript:    Optional[str] = None
    audio_confidence:    Optional[int] = None
    audio_clarity:       Optional[int] = None
    audio_speaking_rate: Optional[str] = None
    audio_pause_count:   Optional[int] = None
    # Video intelligence fields (populated when /api/scoring/video was called)
    video_engagement:    Optional[int] = None   # face presence rate
    video_framing:       Optional[int] = None   # face centering in frame (renamed from video_eye_contact)
    video_stability:     Optional[int] = None   # camera-distance consistency (renamed from video_posture)
    video_movement:      Optional[str] = None   # low|medium|high head movement (renamed from video_stress)


class LearningItem(BaseModel):
    topic: str
    resource: str
    reason: str
    priority: str   # high | medium | low


class FinalReportRequest(BaseModel):
    session_id: str


class FinalReport(BaseModel):
    session_id: str
    candidate_id: str
    candidate_name: str
    selected_role: str
    generated_at: datetime

    # ── Scores ────────────────────────────────────────────────────────────────
    overall_score: int
    technical_score: int
    communication_score: int
    confidence_score: int
    engagement_score: int
    role_fit_score: int
    behavioral_mode: str        # "placeholder" | "audio" | "audio_fallback"

    # ── Qualitative ───────────────────────────────────────────────────────────
    strengths: List[str]
    improvement_areas: List[str]
    recommended_learning_plan: List[LearningItem]
    final_feedback: str

    # ── Per-question breakdown ────────────────────────────────────────────────
    answer_summaries: List[AnswerSummary]

    # ── Phase 11: Diagnostic coaching section (optional — backward compatible) ─
    readiness_level: Optional[str] = None          # "ready" | "almost_ready" | "needs_practice"
    best_fit_roles: Optional[List[str]] = None
    weaker_role_risks: Optional[List[str]] = None
    skill_mastery_summary: Optional[Dict[str, int]] = None
    top_3_strengths_with_evidence: Optional[List[str]] = None
    top_3_gaps_with_evidence: Optional[List[str]] = None
    recommended_7_day_plan: Optional[List[str]] = None
    adaptation_summary: Optional[List[str]] = None
