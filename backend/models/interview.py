from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Question(BaseModel):
    question_id: str
    question: str
    difficulty: str        # easy | medium | hard
    topic: str
    expected_points: List[str]


class EvaluationResult(BaseModel):
    technical_score: int
    depth_score: int
    correctness_score: int
    covered_points: List[str]
    missing_points: List[str]
    feedback: str


class AnswerRecord(BaseModel):
    question_id: str
    question: str
    answer_text: str
    evaluation: EvaluationResult
    answered_at: datetime


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


class EvaluateAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    question: str
    answer: str
    expected_points: List[str]


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
    video_engagement:    Optional[int] = None
    video_eye_contact:   Optional[int] = None
    video_posture:       Optional[int] = None
    video_stress:        Optional[str] = None


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
