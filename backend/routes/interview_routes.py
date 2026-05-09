from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.interview import (
    StartInterviewRequest, StartInterviewResponse,
    InterviewSession, EvaluateAnswerRequest, EvaluationResult, AnswerRecord,
    NextQuestionRequest, NextQuestionResponse,
    FinalReportRequest, FinalReport,
    ImproveAnswerRequest, ImprovedEvaluationResult,
)
from models.analysis import ResumeAnalysis
from agents import interview_orchestrator, evaluator_agent, feedback_agent
from agents import intelligence_engine
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


# ── Start interview ────────────────────────────────────────────────────────────

@router.post("/start", response_model=StartInterviewResponse)
async def start_interview(body: StartInterviewRequest):
    if not body.candidate_id.strip():
        raise HTTPException(status_code=400, detail="candidate_id is required.")
    if not body.selected_role.strip():
        raise HTTPException(status_code=400, detail="selected_role is required.")

    analysis = await _load_analysis(body.candidate_id)

    # ── Phase 11: Build interview plan & initialise candidate state ────────────
    interview_plan = intelligence_engine.build_interview_plan(analysis, body.selected_role)

    # Generate the first question (existing logic)
    session, first_q = await interview_orchestrator.start_session(
        candidate_id=body.candidate_id,
        selected_role=body.selected_role,
        analysis=analysis,
    )

    candidate_state = intelligence_engine.initialize_candidate_state(
        session_id=session.session_id,
        candidate_id=body.candidate_id,
        selected_role=body.selected_role,
        resume_analysis=analysis,
        interview_plan=interview_plan,
    )

    # Agent summary for UI
    level = candidate_state.inferred_level
    strong_count = len(candidate_state.strong_skills)
    weak_count = len(candidate_state.weak_skills)
    plan_topics = ", ".join(item.topic for item in interview_plan[:3])
    agent_summary = (
        f"Inferred level: {level}. "
        f"Detected {strong_count} strong skill area(s) and {weak_count} gap(s) from your resume. "
        f"Interview will cover: {plan_topics}{'…' if len(interview_plan) > 3 else ''}."
    )

    # Persist session with intelligence data
    session_dict = session.model_dump(mode="json")
    plan_list = [item.model_dump() for item in interview_plan]
    state_dict = candidate_state.model_dump()
    session_dict["interview_plan"] = plan_list
    session_dict["candidate_state"] = state_dict
    session_dict["agent_summary"] = agent_summary
    session_dict["decision_traces"] = []
    # Store resume skills so the orchestrator can generate contextual follow-ups
    session_dict["resume_techs"] = analysis.skills[:25] if analysis else []
    # Store project names for personalized question context
    session_dict["resume_projects"] = (
        [{"name": p.name, "technologies": p.technologies[:4]} for p in analysis.projects[:3]]
        if analysis else []
    )

    store.save_session(session.session_id, session_dict)
    if not is_using_memory():
        db = get_db()
        await db["interview_sessions"].insert_one(session_dict)

    return StartInterviewResponse(
        session_id=session.session_id,
        candidate_id=session.candidate_id,
        selected_role=session.selected_role,
        first_question=first_q,
        interview_plan=plan_list,
        agent_summary=agent_summary,
        candidate_state=state_dict,
        inferred_level=level,
    )


# ── Evaluate answer ────────────────────────────────────────────────────────────

@router.post("/evaluate-answer", response_model=EvaluationResult)
async def evaluate_answer(body: EvaluateAnswerRequest):
    if not body.answer.strip():
        raise HTTPException(status_code=400, detail="answer cannot be empty.")

    # Load session to find question topic for rubric
    session_data = store.get_session(body.session_id)
    if not session_data and not is_using_memory():
        db = get_db()
        doc = await db["interview_sessions"].find_one({"session_id": body.session_id})
        if doc:
            doc.pop("_id", None)
            session_data = doc

    # Inject topic into request for rubric scoring
    if session_data:
        questions_asked = session_data.get("questions_asked", [])
        for q in questions_asked:
            if q.get("question_id") == body.question_id:
                body = body.model_copy(update={"topic": q.get("topic", "")})
                break

    result = await evaluator_agent.evaluate(body)

    if session_data:
        record = AnswerRecord(
            question_id=body.question_id,
            question=body.question,
            answer_text=body.answer,
            evaluation=result,
            answered_at=datetime.now(timezone.utc),
        )
        answer_dict = record.model_dump(mode="json")
        # Attach topic to the answer record for intelligence engine
        answer_dict["topic"] = body.topic or ""

        answers = session_data.get("answers", [])
        answers.append(answer_dict)
        session_data["answers"] = answers

        # ── Phase 11: Update candidate state ──────────────────────────────────
        raw_state = session_data.get("candidate_state")
        if raw_state:
            try:
                from models.agent_state import CandidateState
                cs = CandidateState(**raw_state)
                cs = intelligence_engine.update_candidate_state(
                    candidate_state=cs,
                    answer_record=answer_dict,
                )
                session_data["candidate_state"] = cs.model_dump()
            except Exception:
                pass  # non-fatal

        store.save_session(body.session_id, session_data)

        if not is_using_memory():
            db = get_db()
            await db["interview_sessions"].update_one(
                {"session_id": body.session_id},
                {
                    "$push": {"answers": answer_dict},
                    "$set": {"candidate_state": session_data.get("candidate_state")},
                },
            )

    return result


# ── Improve answer (coaching loop retry) ─────────────────────────────────────

@router.post("/improve-answer", response_model=ImprovedEvaluationResult)
async def improve_answer(body: ImproveAnswerRequest):
    """
    Re-evaluate an improved answer for an already-answered question.

    Flow:
      1. Load session and find existing AnswerRecord for question_id.
      2. Build EvaluateAnswerRequest from improved_answer (same plumbing as evaluate-answer).
      3. Run evaluator (full pipeline: semantic + rubric).
      4. Compute delta vs previous_evaluation.
      5. Update AnswerRecord in session (replace, increment attempt_number).
      6. Return ImprovedEvaluationResult.
    """
    if not body.improved_answer.strip():
        raise HTTPException(status_code=400, detail="improved_answer cannot be empty.")
    if body.attempt_number > 3:
        raise HTTPException(status_code=400, detail="Maximum 2 retries per question.")

    session_data = store.get_session(body.session_id)
    if not session_data and not is_using_memory():
        db = get_db()
        doc = await db["interview_sessions"].find_one({"session_id": body.session_id})
        if doc:
            doc.pop("_id", None)
            session_data = doc

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Resolve topic from session if not provided
    topic = body.topic or ""
    if not topic:
        for q in session_data.get("questions_asked", []):
            if q.get("question_id") == body.question_id:
                topic = q.get("topic", "")
                break

    # Build evaluation request for improved answer
    eval_req = EvaluateAnswerRequest(
        session_id=body.session_id,
        question_id=body.question_id,
        question=body.question,
        answer=body.improved_answer,
        expected_points=body.expected_points,
        topic=topic,
    )

    new_result = await evaluator_agent.evaluate(eval_req)

    # ── Compute improvement delta ─────────────────────────────────────────────
    prev = body.previous_evaluation
    prev_tech  = int(prev.get("technical_score",  0))
    prev_depth = int(prev.get("depth_score",      0))
    prev_corr  = int(prev.get("correctness_score", 0))

    previous_scores = {
        "technical":   prev_tech,
        "depth":       prev_depth,
        "correctness": prev_corr,
    }
    improvement_delta = {
        "technical":   new_result.technical_score  - prev_tech,
        "depth":       new_result.depth_score      - prev_depth,
        "correctness": new_result.correctness_score - prev_corr,
    }

    # Concepts newly covered vs previously missing
    prev_missing = set(prev.get("missing_points", []))
    prev_covered = set(prev.get("covered_points", []))
    newly_covered = [p for p in new_result.covered_points if p in prev_missing]
    still_missing = list(new_result.missing_points)

    # ── Update session: replace AnswerRecord, increment attempt_number ────────
    answers = session_data.get("answers", [])
    new_record = AnswerRecord(
        question_id=body.question_id,
        question=body.question,
        answer_text=body.improved_answer,
        evaluation=new_result,
        answered_at=datetime.now(timezone.utc),
        attempt_number=body.attempt_number,
    )
    answer_dict = new_record.model_dump(mode="json")
    answer_dict["topic"] = topic

    # Replace existing record for this question_id, or append
    replaced = False
    for i, a in enumerate(answers):
        if a.get("question_id") == body.question_id:
            answers[i] = answer_dict
            replaced = True
            break
    if not replaced:
        answers.append(answer_dict)

    session_data["answers"] = answers
    store.save_session(body.session_id, session_data)

    if not is_using_memory():
        db = get_db()
        # Replace or push: use arrayFilters for the update
        try:
            await db["interview_sessions"].update_one(
                {"session_id": body.session_id, "answers.question_id": body.question_id},
                {"$set": {"answers.$": answer_dict}},
            )
        except Exception:
            await db["interview_sessions"].update_one(
                {"session_id": body.session_id},
                {"$push": {"answers": answer_dict}},
            )

    return ImprovedEvaluationResult(
        **new_result.model_dump(),
        attempt_number=body.attempt_number,
        previous_scores=previous_scores,
        improvement_delta=improvement_delta,
        newly_covered=newly_covered,
        still_missing=still_missing,
    )


# ── Next question ──────────────────────────────────────────────────────────────

@router.post("/next-question", response_model=NextQuestionResponse)
async def next_question(body: NextQuestionRequest):
    """
    Phase 5 + Phase 11 — Adaptive next question using intelligence engine decision traces.
    """
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

    # ── Phase 11: Try intelligence engine first ────────────────────────────────
    decision_trace = None
    next_q = None
    reason = ""

    raw_state = session_data.get("candidate_state")
    interview_plan_raw = session_data.get("interview_plan", [])
    answers = session_data.get("answers", [])

    if raw_state and answers:
        try:
            from models.agent_state import CandidateState, InterviewPlanItem
            cs = CandidateState(**raw_state)
            plan = [InterviewPlanItem(**item) for item in interview_plan_raw]
            last_answer = answers[-1]
            current_q_dict = questions_asked[-1] if questions_asked else {}

            trace = intelligence_engine.make_next_question_decision(
                candidate_state=cs,
                last_evaluation=last_answer.get("evaluation", {}),
                current_question=current_q_dict,
                interview_plan=plan,
                session_history=[
                    {"question": questions_asked[i], "answer": answers[i]}
                    for i in range(min(len(questions_asked), len(answers)))
                ],
            )
            decision_trace = trace

            # Override the body with intelligence-engine-derived values
            reason = trace.reason_for_adaptation
            next_difficulty = trace.next_difficulty
            # Patch req so orchestrator uses intelligence-engine difficulty
            body = NextQuestionRequest(
                session_id=body.session_id,
                last_answer_score=body.last_answer_score,
                confidence_score=body.confidence_score,
                current_topic=trace.next_topic or body.current_topic,
            )

        except Exception as exc:
            import logging as _lg
            _lg.getLogger(__name__).warning("Intelligence engine failed, using fallback: %s", exc)

    # Fall back to existing orchestrator logic
    next_q_result, orchestrator_reason, session_complete = await interview_orchestrator.next_question(
        req=body, session_data=session_data
    )
    if next_q is None:
        next_q = next_q_result
    if not reason:
        reason = orchestrator_reason

    # Prefer intelligence engine's reason if available
    if decision_trace:
        reason = decision_trace.reason_for_adaptation

    if not session_complete:
        questions_asked.append(next_q.model_dump(mode="json"))
        session_data["questions_asked"] = questions_asked
        session_data["current_question"] = next_q.model_dump(mode="json")

        adaptation_log = session_data.get("adaptation_log", [])
        adaptation_log.append(reason)
        session_data["adaptation_log"] = adaptation_log

        # Store decision trace
        if decision_trace:
            traces = session_data.get("decision_traces", [])
            traces.append(decision_trace.model_dump())
            session_data["decision_traces"] = traces

    else:
        session_data["status"] = "completed"

    store.save_session(body.session_id, session_data)

    if not is_using_memory():
        db = get_db()
        update_payload: dict = {}
        if not session_complete:
            push_items: dict = {
                "questions_asked": next_q.model_dump(mode="json"),
                "adaptation_log": reason,
            }
            if decision_trace:
                push_items["decision_traces"] = decision_trace.model_dump()
            update_payload = {
                "$push": push_items,
                "$set": {"current_question": next_q.model_dump(mode="json")},
            }
        else:
            update_payload = {"$set": {"status": "completed"}}
        await db["interview_sessions"].update_one(
            {"session_id": body.session_id}, update_payload
        )

    questions_answered = n_answered + 1 if session_complete else n_answered
    trace_dict = decision_trace.model_dump() if decision_trace else None
    state_dict = session_data.get("candidate_state")

    return NextQuestionResponse(
        next_question=next_q,
        reason_for_adaptation=reason,
        session_complete=session_complete,
        questions_answered=questions_answered,
        max_questions=5,
        decision_trace=trace_dict,
        candidate_state=state_dict,
    )


# ── Final report ────────────────────────────────────────────────────────────────

@router.post("/final-report", response_model=FinalReport)
async def generate_final_report(body: FinalReportRequest):
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
    analysis = await _load_analysis(candidate_id)

    role = session_data.get("selected_role", "")
    role_fit = 72
    roles_data = store.get_roles(candidate_id)
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

    report = await feedback_agent.generate_report(
        session_data=session_data,
        analysis=analysis,
        role_match_score=role_fit,
    )
    return report


# ── Get session ──────────────────────────────────────────────────────────────

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
