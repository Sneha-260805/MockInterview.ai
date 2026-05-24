import { useEffect, useState, useRef } from "react";
import { useParams, useLocation, Link, useNavigate } from "react-router-dom";
import QuestionPanel from "../components/QuestionPanel";
import EvaluationPanel from "../components/EvaluationPanel";
import AdaptationBadge from "../components/AdaptationBadge";
import InterviewMonitor from "../components/InterviewMonitor";
import InterviewPlanTimeline from "../components/InterviewPlanTimeline";
import AgentTracePanel from "../components/AgentTracePanel";
import { CandidateStatePanel } from "../components/SkillMasteryMap";
import CoachingNudge from "../components/CoachingNudge";
import ImprovementDelta from "../components/ImprovementDelta";
import { getSession, evaluateAnswer, nextQuestion, improveAnswer } from "../services/interviewService";

// ── State machine constants ──────────────────────────────────────────────────
const S  = { loading: "loading", ready: "ready", error: "error" };
const ES = { idle: "idle", evaluating: "evaluating", done: "done", error: "error" };
const NS = { idle: "idle", fetching: "fetching", error: "error" };

// Coaching-loop retry states: NONE → COACHING → RETRYING → COMPARED
const RS = { none: "none", coaching: "coaching", retrying: "retrying", compared: "compared" };
const MAX_RETRIES = 2; // candidate can retry up to 2 times per question (attempts 2 and 3)

// ── Confidence score derived from evaluation + answer length ─────────────────
function deriveConfidence(evaluation, answerText) {
  const wordCount   = answerText.trim().split(/\s+/).length;
  const lengthBonus = Math.min(wordCount / 150, 1) * 20;
  const avg         = (evaluation.technical_score + evaluation.depth_score + evaluation.correctness_score) / 3;
  return Math.min(100, Math.round(avg * 0.8 + lengthBonus));
}

function behavioralConfidence(audioResult, videoResult, evaluation, answerText) {
  if (audioResult?.confidence_score != null && audioResult.status !== "invalid_audio") {
    return audioResult.confidence_score;
  }
  if (videoResult?.status !== "invalid_analysis") {
    const signals = [
      videoResult?.engagement_score,
      videoResult?.framing_score,
      videoResult?.stability_score,
    ].filter((v) => v != null);
    if (signals.length) {
      return Math.round(signals.reduce((sum, v) => sum + v, 0) / signals.length);
    }
  }
  return deriveConfidence(evaluation, answerText);
}

// ── Difficulty colour helper ─────────────────────────────────────────────────
function diffColor(diff) {
  return diff === "hard"
    ? "bg-red-50 text-red-600 border-red-200"
    : diff === "medium"
    ? "bg-yellow-50 text-yellow-600 border-yellow-200"
    : "bg-green-50 text-green-600 border-green-200";
}

// ── Rubric dimension metadata ─────────────────────────────────────────────────
const RUBRIC_META = {
  conceptual_correctness:    { label: "Conceptual Correctness", max: 30 },
  practical_application:     { label: "Practical Application",  max: 25 },
  depth_and_tradeoffs:       { label: "Depth & Trade-offs",     max: 20 },
  communication_structure:   { label: "Communication",          max: 15 },
  resume_project_connection: { label: "Project Connection",     max: 10 },
};

function RubricBar({ dimension, score }) {
  const meta = RUBRIC_META[dimension] || { label: dimension, max: 30 };
  const pct = Math.round((score / meta.max) * 100);
  const color = pct >= 70 ? "bg-green-400" : pct >= 50 ? "bg-yellow-400" : "bg-red-400";
  const textColor = pct >= 70 ? "text-green-700" : pct >= 50 ? "text-yellow-700" : "text-red-600";
  return (
    <div className="mb-2 last:mb-0">
      <div className="flex justify-between mb-1">
        <span className="text-xs text-gray-600">{meta.label}</span>
        <span className={`text-xs font-bold tabular-nums ${textColor}`}>{score}/{meta.max}</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${Math.max(pct, 4)}%` }}
        />
      </div>
    </div>
  );
}

export default function InterviewRoom() {
  const { sessionId } = useParams();
  const location      = useLocation();
  const navigate      = useNavigate();

  // ── Session state ──────────────────────────────────────────────────────────
  const [status,    setStatus]    = useState(location.state?.session ? S.ready : S.loading);
  const [session,   setSession]   = useState(location.state?.session ?? null);
  const [loadError, setLoadError] = useState("");

  // ── Answer / evaluation state ──────────────────────────────────────────────
  const [answer,          setAnswer]          = useState("");
  const [evalStatus,      setEvalStatus]      = useState(ES.idle);
  const [evaluation,      setEvaluation]      = useState(null);
  const [evalError,       setEvalError]       = useState("");
  const [submittedAnswer, setSubmittedAnswer] = useState("");

  // ── Adaptive next-question state ───────────────────────────────────────────
  const [nextStatus,       setNextStatus]       = useState(NS.idle);
  const [nextError,        setNextError]         = useState("");
  const [adaptationReason, setAdaptationReason] = useState("");

  // ── History: [{question, answer, evaluation, reason}] ─────────────────────
  const [history,       setHistory]       = useState([]);
  const [openHistoryIdx, setOpenHistory]  = useState(null);

  // ── Session completion ─────────────────────────────────────────────────────
  const [sessionComplete,   setSessionComplete]   = useState(false);
  const [questionsAnswered, setQuestionsAnswered] = useState(0);
  const maxQuestions = 5;

  // ── Active question ───────────────────────────────────────────────────────
  const [activeQuestion, setActiveQuestion] = useState(null);

  // ── Audio & Video intelligence ─────────────────────────────────────────────
  const [audioResult, setAudioResult] = useState(null);
  const [videoResult, setVideoResult] = useState(null);

  // ── Phase 11: Agent intelligence state ────────────────────────────────────
  const [interviewPlan,  setInterviewPlan]  = useState(location.state?.session?.interview_plan  ?? []);
  const [agentSummary,   setAgentSummary]   = useState(location.state?.session?.agent_summary   ?? "");
  const [candidateState, setCandidateState] = useState(location.state?.session?.candidate_state ?? null);
  const [decisionTrace,  setDecisionTrace]  = useState(null);

  // ── Coaching-loop retry state ─────────────────────────────────────────────
  const [retryStatus,       setRetryStatus]       = useState(RS.none);    // coaching state machine
  const [retryAnswer,       setRetryAnswer]        = useState("");         // editable text in coaching textarea
  const [retryAttempt,      setRetryAttempt]       = useState(2);          // current attempt number
  const [improvedResult,    setImprovedResult]     = useState(null);       // ImprovedEvaluationResult
  const [retryError,        setRetryError]         = useState("");

  // Auto-scroll to evaluation after submit
  const evalRef = useRef(null);

  // ── Load session if not passed via router state ───────────────────────────
  useEffect(() => {
    if (session) {
      const q = session.first_question
             ?? session.current_question
             ?? session.questions_asked?.[0];
      setActiveQuestion(q);
      // Populate Phase 11 data if available
      if (session.interview_plan?.length)  setInterviewPlan(session.interview_plan);
      if (session.agent_summary)           setAgentSummary(session.agent_summary);
      if (session.candidate_state)         setCandidateState(session.candidate_state);
      return;
    }
    if (!sessionId) {
      setLoadError("No session ID in the URL.");
      setStatus(S.error);
      return;
    }
    getSession(sessionId)
      .then((d) => {
        setSession(d);
        setActiveQuestion(d.current_question ?? d.questions_asked?.[0]);
        if (d.interview_plan?.length)  setInterviewPlan(d.interview_plan);
        if (d.agent_summary)           setAgentSummary(d.agent_summary);
        if (d.candidate_state)         setCandidateState(d.candidate_state);
        setStatus(S.ready);
      })
      .catch((e) => {
        setLoadError(e.message || "Could not load session.");
        setStatus(S.error);
      });
  }, [sessionId, session]);

  // Scroll evaluation into view after it appears
  useEffect(() => {
    if (evalStatus === ES.done && evalRef.current) {
      evalRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [evalStatus]);

  // ── Submit answer ──────────────────────────────────────────────────────────
  async function handleSubmit() {
    if (!answer.trim() || evalStatus === ES.evaluating) return;
    setSubmittedAnswer(answer);
    setEvalStatus(ES.evaluating);
    setEvalError("");
    setDecisionTrace(null); // clear trace when submitting new answer

    try {
      const result = await evaluateAnswer({
        sessionId:      session.session_id,
        questionId:     activeQuestion.question_id,
        question:       activeQuestion.question,
        answer,
        expectedPoints: activeQuestion.expected_points,
      });
      setEvaluation(result);
      setEvalStatus(ES.done);
    } catch (err) {
      setEvalError(err.message || "Evaluation failed. Please try again.");
      setEvalStatus(ES.error);
    }
  }

  function handleRetry() {
    setEvalStatus(ES.idle);
    setEvaluation(null);
    setEvalError("");
    setAnswer(submittedAnswer);
  }

  // ── Coaching loop ──────────────────────────────────────────────────────────

  /** Enter coaching mode: prefill retry textarea with last submitted answer. */
  function handleStartCoaching() {
    setRetryAnswer(submittedAnswer);
    setRetryStatus(RS.coaching);
    setRetryError("");
    setImprovedResult(null);
  }

  /** Cancel coaching and go back to the evaluation view. */
  function handleCancelCoaching() {
    setRetryStatus(RS.none);
    setRetryError("");
  }

  /** Submit improved answer for re-evaluation. */
  async function handleImproveSubmit() {
    if (!retryAnswer.trim() || retryStatus === RS.retrying) return;
    setRetryStatus(RS.retrying);
    setRetryError("");

    try {
      const result = await improveAnswer({
        sessionId:          session.session_id,
        questionId:         activeQuestion.question_id,
        question:           activeQuestion.question,
        improvedAnswer:     retryAnswer,
        expectedPoints:     activeQuestion.expected_points,
        previousEvaluation: evaluation,
        attemptNumber:      retryAttempt,
        topic:              activeQuestion.topic,
      });

      setImprovedResult(result);
      setRetryAttempt((prev) => prev + 1);
      setRetryStatus(RS.compared);

      // Update the main evaluation with the latest result so "Next Question"
      // passes the updated score to the intelligence engine.
      setEvaluation(result);
      setSubmittedAnswer(retryAnswer);
    } catch (err) {
      setRetryError(err.message || "Re-evaluation failed. Please try again.");
      setRetryStatus(RS.coaching); // fall back to coaching so user can retry
    }
  }

  /** After seeing the delta, allow another retry if attempts remain. */
  function handleRetryAgain() {
    if (retryAttempt > MAX_RETRIES + 1) return; // +1 because retryAttempt is already incremented
    setRetryAnswer(improvedResult ? (improvedResult.feedback ? retryAnswer : retryAnswer) : retryAnswer);
    setRetryStatus(RS.coaching);
    setRetryError("");
  }

  // ── Fetch next question ────────────────────────────────────────────────────
  async function handleNextQuestion() {
    if (nextStatus === NS.fetching) return;
    setNextStatus(NS.fetching);
    setNextError("");

    const confidence = behavioralConfidence(audioResult, videoResult, evaluation, submittedAnswer);

    try {
      const data = await nextQuestion({
        sessionId:       session.session_id,
        lastAnswerScore: evaluation.technical_score,
        confidenceScore: confidence,
        currentTopic:    activeQuestion.topic,
      });

      // Archive current Q+A into history
      setHistory((prev) => [
        ...prev,
        {
          question:   activeQuestion,
          answer:     submittedAnswer,
          evaluation,
          reason:     adaptationReason || null,
        },
      ]);

      setQuestionsAnswered(data.questions_answered);

      if (data.session_complete) {
        setSessionComplete(true);
        setNextStatus(NS.idle);
        return;
      }

      // Phase 11: capture decision trace & updated state
      if (data.decision_trace)  setDecisionTrace(data.decision_trace);
      if (data.candidate_state) setCandidateState(data.candidate_state);

      // Transition to the new question
      setAdaptationReason(data.reason_for_adaptation);
      setActiveQuestion(data.next_question);
      setAnswer("");
      setSubmittedAnswer("");
      setEvaluation(null);
      setEvalStatus(ES.idle);
      setOpenHistory(null);
      setAudioResult(null);
      setVideoResult(null);
      setNextStatus(NS.idle);
      // Reset coaching state for new question
      setRetryStatus(RS.none);
      setRetryAnswer("");
      setRetryAttempt(2);
      setImprovedResult(null);
      setRetryError("");
    } catch (err) {
      setNextError(err.message || "Could not fetch next question. Please try again.");
      setNextStatus(NS.error);
    }
  }

  // ── Derived ───────────────────────────────────────────────────────────────
  const isEvaluating    = evalStatus === ES.evaluating;
  const isDone          = evalStatus === ES.done;
  const isFetchingNext  = nextStatus === NS.fetching;
  const questionNumber  = history.length + 1;

  // Coaching loop derived
  const isCoaching      = retryStatus === RS.coaching;
  const isRetrying      = retryStatus === RS.retrying;
  const hasCompared     = retryStatus === RS.compared;
  const canRetry        = isDone && retryStatus === RS.none && retryAttempt <= MAX_RETRIES + 1;
  const canRetryAgain   = hasCompared && retryAttempt <= MAX_RETRIES + 1;

  // ── Loading ───────────────────────────────────────────────────────────────
  if (status === S.loading) {
    return (
      <Centered>
        <svg className="w-8 h-8 animate-spin text-brand-500" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        <p className="text-gray-500 text-sm">Loading interview session…</p>
      </Centered>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────
  if (status === S.error) {
    return (
      <Centered>
        <div className="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center">
          <svg className="w-7 h-7 text-red-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <p className="text-gray-700 font-medium">{loadError}</p>
        <Link to="/roles" className="px-5 py-2.5 bg-brand-500 text-white rounded-xl font-semibold text-sm hover:bg-brand-600 transition-colors">
          Back to Role Recommendations
        </Link>
      </Centered>
    );
  }

  // ── Session Complete ───────────────────────────────────────────────────────
  if (sessionComplete) {
    const allEntries = [
      ...history,
      ...(isDone && evaluation
        ? [{ question: activeQuestion, answer: submittedAnswer, evaluation, reason: adaptationReason || null }]
        : []),
    ];
    const totalAnswered = allEntries.length;
    const avgScore      = totalAnswered
      ? Math.round(
          allEntries.reduce(
            (sum, e) =>
              sum + (e.evaluation.technical_score + e.evaluation.depth_score + e.evaluation.correctness_score) / 3,
            0
          ) / totalAnswered
        )
      : 0;

    return (
      <div className="min-h-screen bg-gray-50">
        <TopBar session={session} />
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12 space-y-8">
          {/* Completion header */}
          <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-8 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900">Interview Complete!</h2>
            <p className="text-gray-500 text-sm">
              You answered {totalAnswered} question{totalAnswered !== 1 ? "s" : ""} for{" "}
              <strong>{session.selected_role}</strong>.
            </p>
            <div className="inline-flex items-center gap-2 px-5 py-2 bg-indigo-50 border border-indigo-200 rounded-xl">
              <span className="text-sm text-indigo-600 font-medium">Overall Average</span>
              <span className="text-2xl font-extrabold text-indigo-700 tabular-nums">{avgScore}</span>
              <span className="text-sm text-indigo-400">/100</span>
            </div>
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3 flex-wrap">
              <button
                onClick={() => navigate(`/report/${session.session_id}`)}
                className="w-full sm:w-auto px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold text-sm
                  hover:bg-indigo-700 transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
                </svg>
                View Detailed Report
              </button>
              <Link
                to="/roles"
                className="w-full sm:w-auto px-6 py-3 bg-white border border-gray-200 text-gray-600 rounded-xl
                  font-semibold text-sm hover:border-gray-300 hover:text-gray-800 transition-colors text-center"
              >
                Try Another Role
              </Link>
            </div>
          </div>

          {/* Full history review */}
          <div className="space-y-4">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">
              Full Interview Review
            </p>
            {allEntries.map((entry, idx) => (
              <HistoryCard key={idx} entry={entry} index={idx} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── Main interview room ────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
      <TopBar session={session} />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8 grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">

        {/* ── Left column ───────────────────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Phase 11: Personalised interview plan timeline */}
          {interviewPlan.length > 0 && (
            <InterviewPlanTimeline
              plan={interviewPlan}
              currentStep={questionNumber}
              agentSummary={agentSummary}
            />
          )}

          {/* Adaptation badge (appears from Q2 onward) */}
          {adaptationReason && (
            <AdaptationBadge
              reason={adaptationReason}
              questionNumber={questionNumber}
              maxQuestions={maxQuestions}
              decisionType={decisionTrace?.decision_type}
            />
          )}

          {/* Phase 11: Agent decision trace (shown after next question fetched) */}
          {decisionTrace && (
            <AgentTracePanel trace={decisionTrace} />
          )}

          {/* Active question */}
          {activeQuestion && (
            <QuestionPanel question={activeQuestion} index={questionNumber} />
          )}

          {/* Interview Monitor — placed here so webcam + controls sit directly
              between the question and the answer textarea, eliminating the
              eye-travel problem of having the monitor in a distant sidebar. */}
          <InterviewMonitor
            sessionId={session?.session_id}
            questionNumber={questionNumber}
            onTranscript={(text) => setAnswer((prev) => prev || text)}
            onAudioResult={(data) => setAudioResult(data)}
            onVideoResult={(data) => setVideoResult(data)}
            disabled={isEvaluating}
          />

          {/* Answer section */}
          <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50">
              <span className="text-sm font-semibold text-gray-700">Your Answer</span>
              {isDone && (
                <span className="text-xs text-green-600 font-medium flex items-center gap-1">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  Submitted
                </span>
              )}
              {!isDone && answer.trim() && (
                <span className="text-xs text-gray-400">
                  {answer.trim().split(/\s+/).length} words
                </span>
              )}
            </div>

            {isDone ? (
              <div className="px-6 py-4">
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{submittedAnswer}</p>
              </div>
            ) : (
              <div className="p-6 space-y-4">
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  disabled={isEvaluating}
                  placeholder="Type your answer here, or use the Interview Monitor above to record your answer. STAR method — Situation, Task, Action, Result."
                  rows={7}
                  className="w-full text-sm text-gray-800 placeholder-gray-400 border border-gray-200 rounded-xl
                    px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-brand-400
                    focus:border-transparent leading-relaxed transition-shadow
                    disabled:bg-gray-50 disabled:text-gray-500"
                />

                {evalStatus === ES.error && (
                  <div className="flex items-center justify-between gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
                    <p className="text-sm text-red-700">{evalError}</p>
                    <button onClick={handleRetry} className="text-xs text-red-600 underline shrink-0">Retry</button>
                  </div>
                )}

                <button
                  onClick={handleSubmit}
                  disabled={!answer.trim() || isEvaluating}
                  className="w-full py-3 rounded-xl font-semibold text-white bg-brand-500 hover:bg-brand-600
                    disabled:opacity-40 disabled:cursor-not-allowed transition-colors
                    flex items-center justify-center gap-2"
                >
                  {isEvaluating ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                      Analysing answer and interview signals…
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round"
                          d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                      </svg>
                      Submit Answer
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Evaluation panel */}
          {isDone && evaluation && (
            <div ref={evalRef}>
              <EvaluationPanel evaluation={evaluation} />
            </div>
          )}

          {/* Phase 11: Rubric breakdown */}
          {isDone && evaluation && evaluation.rubric_scores && Object.keys(evaluation.rubric_scores).length > 0 && (
            <div className="bg-white border border-indigo-100 rounded-2xl shadow-sm overflow-hidden">
              <div className="px-5 py-3 bg-indigo-50 border-b border-indigo-100 flex items-center gap-2">
                <svg className="w-4 h-4 text-indigo-500 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                </svg>
                <span className="text-sm font-semibold text-indigo-700">Rubric Breakdown</span>
                {evaluation.evaluation_source && (
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border
                    ${evaluation.evaluation_source.startsWith("llm:")
                      ? "bg-indigo-100 text-indigo-700 border-indigo-200"
                      : "bg-white text-gray-500 border-gray-200"}`}
                  >
                    {evaluation.evaluation_source.startsWith("llm:")
                      ? `AI: ${evaluation.evaluation_source.replace("llm:", "").toUpperCase()}`
                      : "Rule-based"}
                  </span>
                )}
                {evaluation.rubric_total != null && (
                  <span className="ml-auto text-xs font-bold text-indigo-600 tabular-nums">
                    {evaluation.rubric_total}/100
                  </span>
                )}
              </div>
              <div className="p-5 space-y-4">
                {/* Dimension bars */}
                <div>
                  {Object.entries(evaluation.rubric_scores).map(([dim, score]) => (
                    <RubricBar key={dim} dimension={dim} score={score} />
                  ))}
                </div>

                {/* Evidence keywords matched */}
                {evaluation.evidence && evaluation.evidence.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-2">
                      Keywords Detected
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {evaluation.evidence.map((ev, i) => (
                        <span
                          key={i}
                          className="text-[10px] px-2 py-0.5 bg-green-50 border border-green-200 rounded-full text-green-700"
                        >
                          {ev}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Improvement hint */}
                {evaluation.improvement_hint && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                    <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide mb-1">
                      How to Improve
                    </p>
                    <p className="text-xs text-amber-800 leading-relaxed">
                      {evaluation.improvement_hint}
                    </p>
                  </div>
                )}

                {/* Interviewer diagnosis */}
                {evaluation.interviewer_diagnosis && (
                  <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3">
                    <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                      Interviewer View
                    </p>
                    <p className="text-xs text-gray-700 leading-relaxed italic">
                      {evaluation.interviewer_diagnosis}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Coaching loop ─────────────────────────────────────────── */}

          {/* "Try Again" entry CTA — visible right after first evaluation */}
          {canRetry && !isCoaching && !hasCompared && (
            <div className="flex items-center gap-3 px-1">
              <button
                onClick={handleStartCoaching}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold
                  text-amber-700 bg-amber-50 border border-amber-300 hover:bg-amber-100
                  transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                </svg>
                Improve Answer
              </button>
              <p className="text-xs text-gray-400">
                Edit your answer and resubmit to see if you can boost your score.
              </p>
            </div>
          )}

          {/* Coaching nudge panel */}
          {(isCoaching || isRetrying) && (
            <CoachingNudge
              evaluation={improvedResult ?? evaluation}
              answer={retryAnswer}
              onAnswerChange={setRetryAnswer}
              onSubmit={handleImproveSubmit}
              onCancel={handleCancelCoaching}
              isSubmitting={isRetrying}
              attemptNumber={retryAttempt}
            />
          )}

          {/* Error during retry */}
          {retryError && retryStatus === RS.coaching && (
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3">
              <p className="text-sm text-red-700">{retryError}</p>
            </div>
          )}

          {/* Improvement delta panel */}
          {hasCompared && improvedResult && (
            <div className="space-y-3">
              <ImprovementDelta improvedResult={improvedResult} />
              {canRetryAgain && (
                <button
                  onClick={handleRetryAgain}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold
                    text-amber-700 bg-amber-50 border border-amber-300 hover:bg-amber-100
                    transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round"
                      d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                  </svg>
                  Try Once More
                </button>
              )}
            </div>
          )}

          {/* Next question controls */}
          {isDone && !sessionComplete && (
            <div className="space-y-3">
              {nextError && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3">
                  <p className="text-sm text-red-700">{nextError}</p>
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  onClick={handleNextQuestion}
                  disabled={isFetchingNext}
                  className="flex-1 py-3 rounded-xl font-semibold text-white bg-indigo-600 hover:bg-indigo-700
                    disabled:opacity-40 disabled:cursor-not-allowed transition-colors
                    flex items-center justify-center gap-2"
                >
                  {isFetchingNext ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                      AI is selecting next question…
                    </>
                    ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                      </svg>
                      Next Question
                    </>
                  )}
                </button>

                <Link
                  to="/roles"
                  className="px-4 py-3 rounded-xl font-semibold text-gray-600 bg-white border border-gray-200
                    hover:border-gray-300 hover:text-gray-800 transition-colors text-sm"
                >
                  End Session
                </Link>
              </div>

              <p className="text-center text-xs text-gray-400">
                Question {questionNumber} of {maxQuestions} · The AI adapts each question to your last answer
              </p>

              {/* Generate Report — available once 3 questions have been answered */}
              {questionNumber >= 3 && (
                <div className="border-t border-gray-100 pt-4">
                  <button
                    onClick={() => navigate(`/report/${session.session_id}`)}
                    className="w-full py-3 rounded-xl font-semibold text-indigo-700 bg-indigo-50
                      border border-indigo-200 hover:bg-indigo-100 transition-colors text-sm
                      flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round"
                        d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
                    </svg>
                    Generate Final Report
                  </button>
                  <p className="text-center text-xs text-gray-400 mt-2">
                    Get a full AI analysis based on your {questionNumber} answer{questionNumber !== 1 ? "s" : ""} so far
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Question history accordion */}
          {history.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Previous Questions
              </p>
              {history.map((entry, idx) => (
                <HistoryAccordion
                  key={idx}
                  entry={entry}
                  index={idx}
                  isOpen={openHistoryIdx === idx}
                  onToggle={() => setOpenHistory(openHistoryIdx === idx ? null : idx)}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── Right column — sidebar ───────────────────────────────── */}
        <div className="space-y-4">

          {/* Phase 11: Candidate state panel (skill mastery + profile) */}
          {candidateState ? (
            <CandidateStatePanel candidateState={candidateState} />
          ) : (
            <SidebarCard title="Session">
              <InfoRow label="Role"     value={session.selected_role} />
              <InfoRow label="Status"   value={
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                  Active
                </span>
              } />
              <InfoRow label="Progress" value={`${questionNumber} / ${maxQuestions}`} />
              <InfoRow label="Evaluation" value={
                isDone
                  ? <span className="text-green-600 font-medium">Complete</span>
                  : <span className="text-gray-400">Pending</span>
              } />
            </SidebarCard>
          )}

          {/* Progress row when candidateState is showing */}
          {candidateState && (
            <SidebarCard title="Progress">
              <InfoRow label="Role"     value={session.selected_role} />
              <InfoRow label="Question" value={`${questionNumber} / ${maxQuestions}`} />
              {candidateState.inferred_level && (
                <InfoRow label="Level" value={
                  <span className="capitalize px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 text-[10px] font-semibold border border-indigo-100">
                    {candidateState.inferred_level}
                  </span>
                } />
              )}
              <InfoRow label="Evaluation" value={
                isDone
                  ? <span className="text-green-600 font-medium">Complete</span>
                  : <span className="text-gray-400">Pending</span>
              } />
            </SidebarCard>
          )}

          {/* Score summary for current question */}
          {isDone && evaluation && (
            <SidebarCard title="Score Summary">
              <ScoreLine label="Technical"   score={evaluation.technical_score} />
              <ScoreLine label="Depth"       score={evaluation.depth_score} />
              <ScoreLine label="Correctness" score={evaluation.correctness_score} />
              <div className="mt-3 pt-3 border-t border-gray-100">
                <p className="text-xs text-gray-400">
                  Average:{" "}
                  <span className="font-semibold text-gray-700">
                    {Math.round(
                      (evaluation.technical_score + evaluation.depth_score + evaluation.correctness_score) / 3
                    )}
                    /100
                  </span>
                </p>
              </div>
            </SidebarCard>
          )}

          {/* Media scores are shown inside InterviewMonitor above */}

          {/* Running session overview after first Q answered */}
          {history.length >= 1 && (
            <SidebarCard title="Session Overview">
              {history.map((entry, idx) => {
                const avg = Math.round(
                  (entry.evaluation.technical_score + entry.evaluation.depth_score + entry.evaluation.correctness_score) / 3
                );
                const color = avg >= 70 ? "text-green-600" : avg >= 50 ? "text-yellow-500" : "text-orange-500";
                return (
                  <div key={idx} className="flex items-center justify-between mb-2 last:mb-0">
                    <span className="text-xs text-gray-500 truncate max-w-[120px]">
                      Q{idx + 1}: {entry.question.topic}
                    </span>
                    <span className={`text-xs font-bold tabular-nums ${color}`}>{avg}/100</span>
                  </div>
                );
              })}
            </SidebarCard>
          )}

          <div className="hidden lg:block">
            <SidebarCard title="Interview Tips">
              <ul className="space-y-2.5">
                {[
                  "Use the STAR method — Situation, Task, Action, Result.",
                  "Be specific with numbers and outcomes where possible.",
                  "Mention trade-offs — interviewers value nuanced thinking.",
                  "Draw on real projects whenever possible.",
                  "It's fine to pause and structure your thoughts first.",
                ].map((tip, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-gray-600">
                    <span className="mt-0.5 text-brand-400 font-bold shrink-0">{i + 1}.</span>
                    {tip}
                  </li>
                ))}
              </ul>
            </SidebarCard>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function TopBar({ session }) {
  const [copied, setCopied] = useState(false);

  function copySessionId() {
    if (!session?.session_id) return;
    navigator.clipboard.writeText(session.session_id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse shrink-0" />
        <span className="text-sm font-semibold text-gray-800 truncate">{session?.selected_role}</span>
        {session?.session_id && (
          <>
            <span className="text-gray-300 hidden sm:inline">·</span>
            <button
              onClick={copySessionId}
              title="Copy session ID"
              className="hidden sm:flex items-center gap-1 text-xs text-gray-400 font-mono hover:text-gray-700 transition-colors group"
            >
              <span>{session.session_id.slice(0, 8)}…</span>
              {copied ? (
                <svg className="w-3 h-3 text-green-500" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                <svg className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5a3.375 3.375 0 00-3.375-3.375H9.75" />
                </svg>
              )}
            </button>
          </>
        )}
      </div>
      <Link to="/roles" className="text-xs text-gray-400 hover:text-gray-700 transition-colors shrink-0">
        ← Exit
      </Link>
    </div>
  );
}

function HistoryAccordion({ entry, index, isOpen, onToggle }) {
  const avg = Math.round(
    (entry.evaluation.technical_score + entry.evaluation.depth_score + entry.evaluation.correctness_score) / 3
  );
  const avgColor = avg >= 70 ? "text-green-600" : avg >= 50 ? "text-yellow-500" : "text-orange-500";

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xs font-bold text-gray-400 shrink-0">Q{index + 1}</span>
          <span className="text-xs font-medium text-gray-700 truncate">
            {entry.question.question.slice(0, 70)}…
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-2">
          <span className={`text-xs font-bold tabular-nums ${avgColor}`}>{avg}/100</span>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
            fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </div>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-100">
          {/* Topic + difficulty */}
          <div className="flex items-center gap-2 pt-3">
            <span className="text-[10px] text-gray-500 font-medium">{entry.question.topic}</span>
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${diffColor(entry.question.difficulty)}`}>
              {entry.question.difficulty}
            </span>
          </div>

          {/* Full question */}
          <p className="text-sm text-gray-800 leading-relaxed">{entry.question.question}</p>

          {/* Answer */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Your Answer</p>
            <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{entry.answer}</p>
          </div>

          {/* Scores */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Technical",   score: entry.evaluation.technical_score },
              { label: "Depth",       score: entry.evaluation.depth_score },
              { label: "Correctness", score: entry.evaluation.correctness_score },
            ].map(({ label, score }) => {
              const c = score >= 70 ? "text-green-600" : score >= 50 ? "text-yellow-500" : "text-orange-500";
              return (
                <div key={label} className="text-center">
                  <p className={`text-lg font-extrabold tabular-nums ${c}`}>{score}</p>
                  <p className="text-[10px] text-gray-400">{label}</p>
                </div>
              );
            })}
          </div>

          {/* Feedback snippet */}
          {entry.evaluation.feedback && (
            <p className="text-xs text-gray-500 leading-relaxed border-t border-gray-100 pt-3">
              {entry.evaluation.feedback}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Full-detail card used on the session-complete review page */
function HistoryCard({ entry, index }) {
  const avg = Math.round(
    (entry.evaluation.technical_score + entry.evaluation.depth_score + entry.evaluation.correctness_score) / 3
  );
  const avgColor = avg >= 70 ? "text-green-600" : avg >= 50 ? "text-yellow-500" : "text-orange-500";

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold text-gray-500">Q{index + 1}</span>
          <span className="text-xs font-medium text-gray-600">{entry.question.topic}</span>
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${diffColor(entry.question.difficulty)}`}>
            {entry.question.difficulty}
          </span>
        </div>
        <span className={`text-sm font-extrabold tabular-nums ${avgColor}`}>{avg}/100</span>
      </div>

      <div className="p-6 space-y-4">
        {/* AI adaptation reason (for Q2+) */}
        {entry.reason && (
          <div className="flex items-start gap-2 text-xs text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3">
            <svg className="w-3.5 h-3.5 mt-0.5 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
            {entry.reason}
          </div>
        )}

        <p className="text-sm text-gray-800 leading-relaxed font-medium">{entry.question.question}</p>

        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Your Answer</p>
          <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{entry.answer}</p>
        </div>

        <div className="grid grid-cols-3 gap-3 pt-2 border-t border-gray-100">
          {[
            { label: "Technical",   score: entry.evaluation.technical_score },
            { label: "Depth",       score: entry.evaluation.depth_score },
            { label: "Correctness", score: entry.evaluation.correctness_score },
          ].map(({ label, score }) => {
            const c = score >= 70 ? "text-green-600" : score >= 50 ? "text-yellow-500" : "text-orange-500";
            return (
              <div key={label} className="text-center">
                <p className={`text-xl font-extrabold tabular-nums ${c}`}>{score}</p>
                <p className="text-[10px] text-gray-400">{label}</p>
              </div>
            );
          })}
        </div>

        {entry.evaluation.feedback && (
          <p className="text-xs text-gray-500 leading-relaxed">{entry.evaluation.feedback}</p>
        )}
      </div>
    </div>
  );
}

function Centered({ children }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-6">
      {children}
    </div>
  );
}

function SidebarCard({ title, children }) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">{title}</p>
      {children}
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-2 mb-2 last:mb-0">
      <span className="text-xs text-gray-400 shrink-0">{label}</span>
      <span className="text-xs text-gray-700 font-medium text-right">{value}</span>
    </div>
  );
}

function ScoreLine({ label, score }) {
  const color = score >= 70 ? "text-green-600" : score >= 50 ? "text-yellow-500" : "text-orange-500";
  const bar   = score >= 70 ? "bg-green-400"  : score >= 50 ? "bg-yellow-400"  : "bg-orange-400";
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex justify-between mb-1">
        <span className="text-xs text-gray-500">{label}</span>
        <span className={`text-xs font-bold tabular-nums ${color}`}>{score}</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1">
        <div className={`h-1 rounded-full ${bar}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}
