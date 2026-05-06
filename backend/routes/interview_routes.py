from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.interview import (
    StartInterviewRequest, StartInterviewResponse,
    InterviewSession, EvaluateAnswerRequest, EvaluationResult, AnswerRecord,
)
from models.analysis import ResumeAnalysis
from agents import interview_orchestrator, evaluator_agent
from database import store
from database.connection import get_db, is_using_memory

router = APIRouter(prefix="/api/interview", tags=["interview"])


async def _load_analysis(candidate_id: str) -> ResumeAnalysis | None:
    data = store.get_analysis(candidate_id)
    if not data and not is_using_memory():
        db = get_db()
        doc = await db["resume_analysis"].find_one({"candidate_id": candidate_id})
        if doc:
            doc.pop("_id", None)
            data = doc
    return ResumeAnalysis(**data) if data else None


@router.post("/start", response_model=StartInterviewResponse)
async def start_interview(body: StartInterviewRequest):
    if not body.candidate_id.strip():
        raise HTTPException(status_code=400, detail="candidate_id is required.")
    if not body.selected_role.strip():
        raise HTTPException(status_code=400, detail="selected_role is required.")

    analysis = await _load_analysis(body.candidate_id)
    # Analysis is optional — we generate a generic question if it's missing

    session, first_q = await interview_orchestrator.start_session(
        candidate_id=body.candidate_id,
        selected_role=body.selected_role,
        analysis=analysis,
    )

    # Persist session
    session_dict = session.model_dump(mode="json")
    store.save_session(session.session_id, session_dict)
    if not is_using_memory():
        db = get_db()
        await db["interview_sessions"].insert_one(session_dict)

    return StartInterviewResponse(
        session_id=session.session_id,
        candidate_id=session.candidate_id,
        selected_role=session.selected_role,
        first_question=first_q,
    )


@router.post("/evaluate-answer", response_model=EvaluationResult)
async def evaluate_answer(body: EvaluateAnswerRequest):
    if not body.answer.strip():
        raise HTTPException(status_code=400, detail="answer cannot be empty.")

    result = await evaluator_agent.evaluate(body)

    # Persist the answer record inside the session
    session_data = store.get_session(body.session_id)
    if session_data:
        record = AnswerRecord(
            question_id=body.question_id,
            question=body.question,
            answer_text=body.answer,
            evaluation=result,
            answered_at=datetime.now(timezone.utc),
        )
        answers = session_data.get("answers", [])
        answers.append(record.model_dump(mode="json"))
        session_data["answers"] = answers
        store.save_session(body.session_id, session_data)

        if not is_using_memory():
            db = get_db()
            await db["interview_sessions"].update_one(
                {"session_id": body.session_id},
                {"$push": {"answers": record.model_dump(mode="json")}},
            )

    return result


@router.get("/{session_id}", response_model=InterviewSession)
async def get_session(session_id: str):
    data = store.get_session(session_id)
    if not data and not is_using_memory():
        db = get_db()
        doc = await db["interview_sessions"].find_one({"session_id": session_id})
        if doc:
            doc.pop("_id", None)
            data = doc

    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")

    return InterviewSession(**data)
