import { useEffect, useState, useRef } from "react";
import { useParams, useLocation, Link, useNavigate } from "react-router-dom";
import QuestionPanel from "../components/QuestionPanel";
import EvaluationPanel from "../components/EvaluationPanel";
import AdaptationBadge from "../components/AdaptationBadge";
import AgentTracePanel from "../components/AgentTracePanel";
import AudioRecorder from "../components/AudioRecorder";
import VideoRecorder from "../components/VideoRecorder";
import { getSession, evaluateAnswer, nextQuestion } from "../services/interviewService";

// ── State machine constants ──────────────────────────────────────────────────
const S  = { loading: "loading", ready: "ready", error: "error" };
const ES = { idle: "idle", evaluating: "evaluating", done: "done", error: "error" };
const NS = { idle: "idle", fetching: "fetching", error: "error" };

// ── Confidence score derived from evaluation + answer length ─────────────────
function deriveConfidence(evaluation, answerText) {
  const wordCount   = answerText.trim().split(/\s+/).length;
  const lengthBonus = Math.min(wordCount / 150, 1) * 20; // up to +20 pts for length
  const avg         = (evaluation.technical_score + evaluation.depth_score + evaluation.correctness_score) / 3;
  return Math.min(100, Math.round(avg * 0.8 + lengthBonus));
}

// ── Difficulty colour helper ─────────────────────────────────────────────────
function diffColor(diff) {
  return diff === "hard"
    ? "bg-red-50 text-red-600 border-red-200"
    : diff === "medium"
    ? "bg-yellow-50 text-yellow-600 border-yellow-200"
    : "bg-green-50 text-green-600 border-green-200";
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

  // ── Active question (what's currently on screen) ──────────────────────────
  const [activeQuestion, setActiveQuestion] = useState(null);

  // ── Audio & Video intelligence ─────────────────────────────────────────────
  const [audioResult, setAudioResult] = useState(null);
  const [videoResult, setVideoResult] = useState(null);

  // Auto-scroll to evaluation after submit
  const evalRef = useRef(null);

  // ── Load session if not passed via router state ───────────────────────────
  useEffect(() => {
    if (session) {
      // StartInterviewResponse  → first_question
      // InterviewSession (GET)  → current_question | questions_asked[0]
      const q = session.first_question
             ?? session.current_question
             ?? session.questions_asked?.[0];
      setActiveQuestion(q);
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

  // ── Fetch next question ────────────────────────────────────────────────────
  async function handleNextQuestion() {
    if (nextStatus === NS.fetching) return;
    setNextStatus(NS.fetching);
    setNextError("");

    const confidence = deriveConfidence(evaluation, submittedAnswer);

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
    } catch (err) {
      setNextError(err.message || "Could not fetch next question. Please try again.");
      setNextStatus(NS.error);
    }
  }

  // ── Derived ───────────────────────────────────────────────────────────────
  const isEvaluating   = evalStatus === ES.evaluating;
  const isDone         = evalStatus === ES.done;
  const isFetchingNext = nextStatus === NS.fetching;
  const questionNumber = history.length + 1;

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

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── Left column ───────────────────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Adaptation badge (appears from Q2 onward) */}
          {adaptationReason && (
            <AdaptationBadge
              reason={adaptationReason}
              questionNumber={questionNumber}
              maxQuestions={maxQuestions}
            />
          )}

          {/* Agent Decision Trace — shown from Q2 onward alongside adaptation badge */}
          {adaptationReason && !isDone && history.length > 0 && (() => {
            const lastEntry = history[history.length - 1];
            return (
              <AgentTracePanel
                evaluation={lastEntry.evaluation}
                adaptationReason={adaptationReason}
                prevQuestion={lastEntry.question}
                nextQuestion={activeQuestion}
                confidenceScore={deriveConfidence(lastEntry.evaluation, lastEntry.answer)}
              />
            );
          })()}

          {/* Active question */}
          {activeQuestion && (
            <QuestionPanel question={activeQuestion} index={questionNumber} />
          )}

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
                  placeholder="Type your answer here. Use the STAR method — be specific, give examples, discuss trade-offs."
                  rows={7}
                  className="w-full text-sm text-gray-800 placeholder-gray-400 border border-gray-200 rounded-xl
                    px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-brand-400
                    focus:border-transparent leading-relaxed transition-shadow
                    disabled:bg-gray-50 disabled:text-gray-500"
                />

                {/* Audio recorder (optional) */}
                <AudioRecorder
                  sessionId={session?.session_id}
                  questionNumber={questionNumber}
                  onTranscript={(text) => setAnswer((prev) => prev || text)}
                  onResult={(data) => setAudioResult(data)}
                  disabled={isEvaluating}
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
                      Evaluating your answer…
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

          {/* Agent Trace — shown after next-question is selected (Q2+) */}
          {isDone && evaluation && adaptationReason && (
            <AgentTracePanel
              evaluation={evaluation}
              adaptationReason={adaptationReason}
              prevQuestion={activeQuestion}
              nextQuestion={null}
              confidenceScore={deriveConfidence(evaluation, submittedAnswer)}
            />
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

          {/* Video monitor — always at top of sidebar */}
          <VideoRecorder
            sessionId={session?.session_id}
            questionNumber={questionNumber}
            onResult={(data) => setVideoResult(data)}
            disabled={isEvaluating}
          />

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

          {/* Audio scores sidebar card */}
          {audioResult && (
            <SidebarCard title="Audio Scores">
              <ScoreLine label="Confidence" score={audioResult.confidence_score} />
              <ScoreLine label="Clarity"    score={audioResult.communication_clarity_score} />
              <div className="mt-2 pt-2 border-t border-gray-100 space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Pace</span>
                  <span className={`font-semibold capitalize
                    ${audioResult.speaking_rate === "medium" ? "text-green-600"
                      : audioResult.speaking_rate === "fast" ? "text-orange-500"
                      : "text-blue-500"}`}>
                    {audioResult.speaking_rate}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Pauses</span>
                  <span className="font-semibold text-gray-700">{audioResult.pause_count}</span>
                </div>
                {audioResult.mode === "fallback" && (
                  <p className="text-[10px] text-amber-600 pt-1">
                    Heuristic mode — install faster-whisper for real transcription
                  </p>
                )}
              </div>
            </SidebarCard>
          )}

          {/* Video scores sidebar card */}
          {videoResult && (
            <SidebarCard title="Video Scores">
              <ScoreLine label="Engagement"  score={videoResult.engagement_score} />
              <ScoreLine label="Eye Contact" score={videoResult.eye_contact_score} />
              <ScoreLine label="Posture"     score={videoResult.posture_score} />
              <div className="mt-2 pt-2 border-t border-gray-100 space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Stress</span>
                  <span className={`font-semibold capitalize
                    ${videoResult.stress_indicator === "low"    ? "text-green-600"
                      : videoResult.stress_indicator === "medium" ? "text-yellow-500"
                      : "text-red-500"}`}>
                    {videoResult.stress_indicator === "low" ? "Calm"
                      : videoResult.stress_indicator === "medium" ? "Moderate"
                      : "Elevated"}
                  </span>
                </div>
                {videoResult.mode === "fallback" && (
                  <p className="text-[10px] text-amber-600 pt-1">
                    Heuristic mode — install opencv-python for real analysis
                  </p>
                )}
              </div>
            </SidebarCard>
          )}

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
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function TopBar({ session }) {
  return (
    <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-sm font-semibold text-gray-800">{session?.selected_role}</span>
        <span className="text-gray-300">·</span>
        <span className="text-xs text-gray-400 font-mono hidden sm:inline">{session?.session_id}</span>
      </div>
      <Link to="/roles" className="text-xs text-gray-400 hover:text-gray-700 transition-colors">
        ← Exit interview
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
