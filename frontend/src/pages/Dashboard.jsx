import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

const QUICK_ACTIONS = [
  {
    to: "/upload",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    label: "Upload Resume",
    desc: "Start fresh — upload a PDF or text resume to get role & job recommendations.",
    cta: "Upload →",
    accent: "blue",
  },
  {
    to: "/roles",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    label: "View Role Recommendations",
    desc: "See which engineering roles best match your most recently uploaded resume.",
    cta: "View roles →",
    accent: "violet",
  },
  {
    to: "/jobs",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
    label: "Browse Job Matches",
    desc: "Top-10 job listings from our 50-listing database ranked by your skill fit.",
    cta: "View jobs →",
    accent: "emerald",
  },
];

const HOW_IT_WORKS = [
  { step: "1", title: "Upload & Analyse", body: "Drag in your resume — the AI extracts skills, experience, projects, and gaps in seconds." },
  { step: "2", title: "Pick a Role", body: "Your skills are matched against 8 engineering role profiles. Choose the one you want to practice." },
  { step: "3", title: "Practice Adaptively", body: "Answer 5 questions that get harder or easier based on your live scores." },
  { step: "4", title: "Review Your Report", body: "Radar chart, per-question bar chart, audio/video behavioral scores, and a personalised learning plan." },
];

const ACCENT_CLASSES = {
  blue:    { icon: "bg-blue-50 text-blue-600",   ring: "hover:border-blue-200",   cta: "text-blue-600 hover:text-blue-700" },
  violet:  { icon: "bg-violet-50 text-violet-600", ring: "hover:border-violet-200", cta: "text-violet-600 hover:text-violet-700" },
  emerald: { icon: "bg-emerald-50 text-emerald-600", ring: "hover:border-emerald-200", cta: "text-emerald-600 hover:text-emerald-700" },
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [candidateId, setCandidateId] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [resumeInput, setResumeInput] = useState("");
  const [resumeError, setResumeError] = useState("");

  useEffect(() => {
    setCandidateId(localStorage.getItem("candidate_id"));
    setSessionId(localStorage.getItem("last_session_id"));
  }, []);

  function handleResumeSession(e) {
    e.preventDefault();
    const id = resumeInput.trim();
    if (!id) { setResumeError("Please enter a session ID."); return; }
    if (id.length < 8) { setResumeError("Session ID looks too short — please check and try again."); return; }
    setResumeError("");
    navigate(`/interview/${id}`);
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-12 space-y-12">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-1">Dashboard</h1>
        <p className="text-gray-500 text-base">
          Pick up where you left off, or start a new interview session.
        </p>
      </div>

      {/* Saved session banner */}
      {(candidateId || sessionId) && (
        <div className="bg-brand-50 border border-brand-500/20 rounded-2xl p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex-1">
            <p className="text-sm font-semibold text-brand-700 mb-0.5">Session detected</p>
            <p className="text-xs text-brand-500">
              {candidateId && <span>Resume ID: <code className="font-mono">{candidateId.slice(0, 8)}…</code></span>}
              {candidateId && sessionId && " · "}
              {sessionId && <span>Last session: <code className="font-mono">{sessionId.slice(0, 8)}…</code></span>}
            </p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            {candidateId && (
              <button
                onClick={() => navigate(`/roles/${candidateId}`)}
                className="px-4 py-2 text-sm bg-brand-500 hover:bg-brand-600 text-white rounded-xl font-medium transition-colors"
              >
                View Roles
              </button>
            )}
            {sessionId && (
              <button
                onClick={() => navigate(`/report/${sessionId}`)}
                className="px-4 py-2 text-sm border border-brand-500/30 text-brand-600 hover:bg-brand-50 rounded-xl font-medium transition-colors"
              >
                Last Report
              </button>
            )}
          </div>
        </div>
      )}

      {/* Resume session by ID */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Resume a Session</h2>
        <form onSubmit={handleResumeSession} className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
          <div className="flex-1 relative">
            <input
              type="text"
              value={resumeInput}
              onChange={(e) => { setResumeInput(e.target.value); setResumeError(""); }}
              placeholder="Paste a session ID to continue…"
              className="w-full text-sm text-gray-800 placeholder-gray-400 border border-gray-200 rounded-xl
                px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent transition-shadow"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2.5 bg-brand-500 hover:bg-brand-600 text-white rounded-xl font-semibold text-sm
              transition-colors shrink-0 flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
            Go to Session
          </button>
        </form>
        {resumeError && (
          <p className="text-xs text-red-600 mt-2">{resumeError}</p>
        )}
        <p className="text-[11px] text-gray-400 mt-2">
          Your session ID is shown in the interview room header (e.g. <code className="font-mono">a3f8c1…</code>).
          Sessions are auto-saved — paste the ID to pick up where you left off.
        </p>
      </section>

      {/* Quick Actions */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
          {QUICK_ACTIONS.map((action) => {
            const ac = ACCENT_CLASSES[action.accent];
            const target = candidateId
              ? action.to === "/roles" ? `/roles/${candidateId}` : action.to === "/jobs" ? `/jobs/${candidateId}` : action.to
              : action.to;
            return (
              <Link
                key={action.label}
                to={target}
                className={`bg-white border border-gray-100 rounded-2xl p-6 flex flex-col gap-4 shadow-sm transition-all ${ac.ring} hover:shadow-md`}
              >
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${ac.icon}`}>
                  {action.icon}
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-800 text-sm mb-1">{action.label}</h3>
                  <p className="text-xs text-gray-400 leading-relaxed">{action.desc}</p>
                </div>
                <span className={`text-sm font-semibold ${ac.cta} transition-colors`}>{action.cta}</span>
              </Link>
            );
          })}
        </div>
      </section>

      {/* How it works */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-4">How it works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {HOW_IT_WORKS.map((item, i) => (
            <div key={item.step} className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm relative overflow-hidden">
              <span className="absolute top-3 right-4 text-5xl font-black text-gray-50 select-none leading-none">
                {item.step}
              </span>
              <div className="w-8 h-8 rounded-lg bg-brand-500 text-white font-bold text-sm flex items-center justify-center mb-3 relative">
                {item.step}
              </div>
              <h3 className="font-semibold text-gray-800 text-sm mb-1 relative">{item.title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed relative">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer CTA */}
      <section className="text-center pt-4 pb-2">
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 px-8 py-3.5 bg-brand-500 hover:bg-brand-600 text-white rounded-xl font-semibold text-base transition-colors shadow-md shadow-brand-500/25"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          Upload Resume to Begin
        </Link>
      </section>
    </div>
  );
}
