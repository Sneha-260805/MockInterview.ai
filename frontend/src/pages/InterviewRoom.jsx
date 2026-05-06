import { useEffect, useState } from "react";
import { useParams, useLocation, Link } from "react-router-dom";
import QuestionPanel from "../components/QuestionPanel";
import EvaluationPanel from "../components/EvaluationPanel";
import { getSession, evaluateAnswer } from "../services/interviewService";

const S = { loading: "loading", ready: "ready", error: "error" };
const ES = { idle: "idle", evaluating: "evaluating", done: "done", error: "error" };

export default function InterviewRoom() {
  const { sessionId } = useParams();
  const location = useLocation();

  const [status, setStatus] = useState(location.state?.session ? S.ready : S.loading);
  const [session, setSession] = useState(location.state?.session ?? null);
  const [loadError, setLoadError] = useState("");

  const [answer, setAnswer] = useState("");
  const [evalStatus, setEvalStatus] = useState(ES.idle);
  const [evaluation, setEvaluation] = useState(null);
  const [evalError, setEvalError] = useState("");
  const [submittedAnswer, setSubmittedAnswer] = useState("");   // locked copy for display

  useEffect(() => {
    if (session) return;
    if (!sessionId) { setLoadError("No session ID in the URL."); setStatus(S.error); return; }
    getSession(sessionId)
      .then((d) => { setSession(d); setStatus(S.ready); })
      .catch((e) => { setLoadError(e.message || "Could not load session."); setStatus(S.error); });
  }, [sessionId, session]);

  async function handleSubmit() {
    if (!answer.trim() || evalStatus === ES.evaluating) return;

    const q = currentQuestion;
    setSubmittedAnswer(answer);          // lock the answer for display
    setEvalStatus(ES.evaluating);
    setEvalError("");

    try {
      const result = await evaluateAnswer({
        sessionId: session.session_id,
        questionId: q.question_id,
        question: q.question,
        answer,
        expectedPoints: q.expected_points,
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
    // Keep submittedAnswer so the user can re-submit the same or edit
    setAnswer(submittedAnswer);
  }

  const currentQuestion = session?.current_question ?? session?.questions_asked?.[0];
  const questionIndex = session?.questions_asked?.length ?? 1;
  const isEvaluating = evalStatus === ES.evaluating;
  const isDone = evalStatus === ES.done;

  // ── Loading ──────────────────────────────────────────────────────────────
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

  // ── Error ────────────────────────────────────────────────────────────────
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

  // ── Interview room ────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm font-semibold text-gray-800">{session.selected_role}</span>
          <span className="text-gray-300">·</span>
          <span className="text-xs text-gray-400 font-mono hidden sm:inline">{session.session_id}</span>
        </div>
        <Link to="/roles" className="text-xs text-gray-400 hover:text-gray-700 transition-colors">
          ← Exit interview
        </Link>
      </div>

      {/* Main layout */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── Left column ─────────────────────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Question — always visible */}
          <QuestionPanel question={currentQuestion} index={questionIndex} />

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

            {/* After submission — show locked answer as read-only */}
            {isDone ? (
              <div className="px-6 py-4">
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {submittedAnswer}
                </p>
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

                {evalStatus === ES.error && (
                  <div className="flex items-center justify-between gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
                    <p className="text-sm text-red-700">{evalError}</p>
                    <button onClick={handleRetry} className="text-xs text-red-600 underline shrink-0">
                      Retry
                    </button>
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

          {/* Evaluation panel — appears after submission */}
          {isDone && evaluation && <EvaluationPanel evaluation={evaluation} />}

          {/* Phase 5 hint after evaluation */}
          {isDone && (
            <div className="text-center py-2">
              <p className="text-xs text-gray-400">
                Adaptive follow-up questions arriving in Phase 5 ·{" "}
                <Link to="/roles" className="text-brand-500 hover:underline">
                  Try another role
                </Link>
              </p>
            </div>
          )}
        </div>

        {/* ── Right column — sidebar ───────────────────────────────────── */}
        <div className="space-y-4">
          <SidebarCard title="Session">
            <InfoRow label="Role" value={session.selected_role} />
            <InfoRow label="Status" value={
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                Active
              </span>
            } />
            <InfoRow label="Question" value={`${questionIndex} of N`} />
            <InfoRow label="Evaluation" value={
              isDone
                ? <span className="text-green-600 font-medium">Complete</span>
                : <span className="text-gray-400">Pending</span>
            } />
          </SidebarCard>

          {isDone && evaluation && (
            <SidebarCard title="Score Summary">
              <ScoreLine label="Technical" score={evaluation.technical_score} />
              <ScoreLine label="Depth" score={evaluation.depth_score} />
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

          <SidebarCard title="Interview Tips">
            <ul className="space-y-2.5">
              {[
                "Use the STAR method — Situation, Task, Action, Result.",
                "Be specific with numbers and outcomes where possible.",
                "It's fine to pause and structure your thoughts first.",
                "Mention trade-offs — interviewers value nuanced thinking.",
                "Draw on real projects from your resume whenever possible.",
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

// ── Helper components ─────────────────────────────────────────────────────────

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
  const bar = score >= 70 ? "bg-green-400" : score >= 50 ? "bg-yellow-400" : "bg-orange-400";
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
