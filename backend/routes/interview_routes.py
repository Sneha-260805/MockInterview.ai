from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.interview import (
    StartInterviewRequest, StartInterviewResponse,
    InterviewSession, EvaluateAnswerRequest, EvaluationResult, AnswerRecord,
    NextQuestionRequest, NextQuestionResponse,
    FinalReportRequest, FinalReport,
)
from models.analysis import ResumeAnalysis
from agents import interview_orchestrator, evaluator_agent, feedback_agent
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


@router.post("/next-question", response_model=NextQuestionResponse)
async def next_question(body: NextQuestionRequest):
    """
    Phase 5 — Adaptive next question.
    Reads the persisted session, runs the orchestrator's adaptive logic,
    appends the new question to questions_asked, and returns the result.
    """
    # Load session
    session_data = store.get_session(body.session_id)
    if not session_data and not is_using_memory():
        db = get_db()
        doc = await db["interview_sessions"].find_one({"session_id": body.session_id})
        if doc:
            doc.pop("_id", None)
            session_data = doc

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session_data.get("status") == "completed":
        raise HTTPException(status_code=400, detail="Session already completed.")

    n_answered = len(session_data.get("answers", []))
    questions_asked = session_data.get("questions_asked", [])

    # Delegate to orchestrator
    next_q, reason, session_complete = await interview_orchestrator.next_question(
        req=body, session_data=session_data
    )

    if not session_complete:
        # Append question and log the adaptation reason for the report
        questions_asked.append(next_q.model_dump(mode="json"))
        session_data["questions_asked"]  = questions_asked
        session_data["current_question"] = next_q.model_dump(mode="json")

        adaptation_log = session_data.get("adaptation_log", [])
        adaptation_log.append(reason)
        session_data["adaptation_log"] = adaptation_log
    else:
        session_data["status"] = "completed"

    store.save_session(body.session_id, session_data)

    if not is_using_memory():
        db = get_db()
        update_payload: dict = {}
        if not session_complete:
            update_payload = {
                "$push": {
                    "questions_asked": next_q.model_dump(mode="json"),
                    "adaptation_log": reason,
                },
                "$set": {"current_question": next_q.model_dump(mode="json")},
            }
        else:
            update_payload = {"$set": {"status": "completed"}}
        await db["interview_sessions"].update_one(
            {"session_id": body.session_id}, update_payload
        )

    questions_answered = n_answered + 1 if session_complete else n_answered

    return NextQuestionResponse(
        next_question=next_q,
        reason_for_adaptation=reason,
        session_complete=session_complete,
        questions_answered=questions_answered,
        max_questions=5,
    )


@router.post("/final-report", response_model=FinalReport)
async def generate_final_report(body: FinalReportRequest):
    """
    Phase 6 — Generate a comprehensive final feedback report for the session.
    Combines all answered Q&As, evaluations, adaptation reasons, and resume
    analysis into a scored, actionable report with a personalised learning plan.
    """
    # ── Load session ──────────────────────────────────────────────────────────
    session_data = store.get_session(body.session_id)
    if not session_data and not is_using_memory():
        db = get_db()
        doc = await db["interview_sessions"].find_one({"session_id": body.session_id})
        if doc:
            doc.pop("_id", None)
            session_data = doc

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    answers = session_data.get("answers", [])
    if not answers:
        raise HTTPException(
            status_code=400,
            detail="No answers on record. Answer at least one question before generating the report.",
        )

    candidate_id = session_data.get("candidate_id", "")

    # ── Load resume analysis (optional) ──────────────────────────────────────
    analysis = await _load_analysis(candidate_id)

    # ── Load role-fit score from stored recommendation ────────────────────────
    role        = session_data.get("selected_role", "")
    role_fit    = 72   # default
    roles_data  = store.get_roles(candidate_id)
    if not roles_data and not is_using_memory():
        db = get_db()
        doc = await db["role_recommendations"].find_one({"candidate_id": candidate_id})
        if doc:
            doc.pop("_id", None)
            roles_data = doc
    if roles_data:
        for r in roles_data.get("recommended_roles", []):
            if r.get("role") == role:
                role_fit = int(r.get("match_score", 72))
                break

    # ── Delegate to feedback agent ────────────────────────────────────────────
    report = await feedback_agent.generate_report(
        session_data=session_data,
        analysis=analysis,
        role_match_score=role_fit,
    )
    return report


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
