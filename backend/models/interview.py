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
