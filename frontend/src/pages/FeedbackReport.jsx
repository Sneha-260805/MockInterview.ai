import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";

import ScoreCard    from "../components/ScoreCard";
import ReportSection from "../components/ReportSection";
import SkillMasteryMap from "../components/SkillMasteryMap";
import { generateFinalReport } from "../services/interviewService";

// ── Colour helpers ─────────────────────────────────────────────────────────────
const priorityStyles = {
  high:   "bg-red-50   text-red-600   border-red-200",
  medium: "bg-yellow-50 text-yellow-600 border-yellow-200",
  low:    "bg-green-50  text-green-600  border-green-200",
};

function scoreColor(s) {
  return s >= 70 ? "text-green-600" : s >= 50 ? "text-yellow-500" : "text-orange-500";
}

// ── Readiness level config ─────────────────────────────────────────────────────
const READINESS_CONFIG = {
  ready: {
    label: "Interview Ready",
    color: "bg-green-50 border-green-200 text-green-700",
    dot:   "bg-green-500",
    icon:  "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    desc:  "You demonstrated strong command of the core concepts and communicated clearly.",
  },
  almost_ready: {
    label: "Almost Ready",
    color: "bg-yellow-50 border-yellow-200 text-yellow-700",
    dot:   "bg-yellow-500",
    icon:  "M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z",
    desc:  "Good foundation — a focused week of practice on your growth areas will get you over the line.",
  },
  needs_practice: {
    label: "Needs Practice",
    color: "bg-red-50 border-red-200 text-red-700",
    dot:   "bg-red-500",
    icon:  "M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z",
    desc:  "Keep practising — review the 7-day plan below and focus on the identified gaps.",
  },
};

// ── Custom Recharts tooltip ───────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-md px-4 py-3 text-xs">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <strong>{p.value}</strong>
        </p>
      ))}
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────
const IconStar = () => (
  <svg className="w-3.5 h-3.5 text-indigo-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
  </svg>
);
const IconTarget = () => (
  <svg className="w-3.5 h-3.5 text-orange-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
  </svg>
);
const IconBook = () => (
  <svg className="w-3.5 h-3.5 text-blue-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
  </svg>
);
const IconChat = () => (
  <svg className="w-3.5 h-3.5 text-purple-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.5 48.172 48.172 0 003.423-.38c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
  </svg>
);
const IconList = () => (
  <svg className="w-3.5 h-3.5 text-gray-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
  </svg>
);
const IconBrain = () => (
  <svg className="w-3.5 h-3.5 text-indigo-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
  </svg>
);
const IconCalendar = () => (
  <svg className="w-3.5 h-3.5 text-green-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5m-9-6h.008v.008H12v-.008zM12 15h.008v.008H12V15zm0 2.25h.008v.008H12v-.008zM9.75 15h.008v.008H9.75V15zm0 2.25h.008v.008H9.75v-.008zM7.5 15h.008v.008H7.5V15zm0 2.25h.008v.008H7.5v-.008zm6.75-4.5h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V15zm0 2.25h.008v.008h-.008v-.008zm2.25-4.5h.008v.008H16.5v-.008zm0 2.25h.008v.008H16.5V15z" />
  </svg>
);


const REPORT_TIMEOUT_MS = 30_000;

function withTimeout(promise, ms) {
  const timer = new Promise((_, reject) =>
    setTimeout(() => reject(new Error("Report generation timed out. The AI is taking longer than usual — please retry.")), ms)
  );
  return Promise.race([promise, timer]);
}

export default function FeedbackReport() {
  const { sessionId } = useParams();
  const [report,     setReport]     = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!sessionId) { setError("No session ID in the URL."); setLoading(false); return; }
    setLoading(true);
    setError("");
    withTimeout(generateFinalReport(sessionId), REPORT_TIMEOUT_MS)
      .then(setReport)
      .catch((e) => setError(e.message || "Could not generate report."))
      .finally(() => setLoading(false));
  }, [sessionId, retryCount]);

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
        <svg className="w-10 h-10 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        <p className="text-gray-500 text-sm">Generating your personalised report…</p>
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────────
  if (error || !report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4 text-center px-6">
        <div className="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center">
          <svg className="w-7 h-7 text-red-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <p className="text-gray-700 font-medium max-w-sm">{error || "Report unavailable."}</p>
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <button
            onClick={() => setRetryCount((c) => c + 1)}
            className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-semibold text-sm hover:bg-indigo-700 transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            Retry
          </button>
          <Link to="/roles" className="px-5 py-2.5 bg-white border border-gray-200 text-gray-600 rounded-xl font-semibold text-sm hover:border-gray-300 transition-colors">
            Back to Roles
          </Link>
        </div>
      </div>
    );
  }

  // ── Chart data ─────────────────────────────────────────────────────────────
  const radarData = [
    { subject: "Technical",     score: report.technical_score,     fullMark: 100 },
    { subject: "Communication", score: report.communication_score, fullMark: 100 },
    { subject: "Confidence",    score: report.confidence_score,    fullMark: 100 },
    { subject: "Engagement",    score: report.engagement_score,    fullMark: 100 },
    { subject: "Role Fit",      score: report.role_fit_score,      fullMark: 100 },
  ];

  const barData = report.answer_summaries.map((s) => ({
    name:        `Q${s.question_number}`,
    Technical:   s.technical_score,
    Depth:       s.depth_score,
    Correctness: s.correctness_score,
  }));

  const overallColor = scoreColor(report.overall_score);

  // Phase 11: readiness config
  const readiness = report.readiness_level
    ? (READINESS_CONFIG[report.readiness_level] || READINESS_CONFIG.almost_ready)
    : null;

  // ── Report ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50 pb-16">
      {/* ── Sticky header ────────────────────────────────────────────────── */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-gray-800">Final Report</span>
          <span className="text-gray-300">·</span>
          <span className="text-xs text-gray-500">{report.selected_role}</span>
          {readiness && (
            <>
              <span className="text-gray-300">·</span>
              <span className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full border ${readiness.color}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${readiness.dot}`} />
                {readiness.label}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.print()}
            className="text-xs text-gray-500 hover:text-gray-800 transition-colors flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5zm-3 0h.008v.008H15V10.5z" />
            </svg>
            Print
          </button>
          <Link to="/roles" className="text-xs text-gray-400 hover:text-gray-700 transition-colors">
            ← Back to Roles
          </Link>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 pt-8 space-y-6">

        {/* ── Hero ─────────────────────────────────────────────────────────── */}
        <div className="bg-gradient-to-br from-indigo-600 to-indigo-800 rounded-2xl shadow-lg p-8 text-white">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div>
              <p className="text-indigo-200 text-xs font-semibold uppercase tracking-wider mb-1">
                Mock Interview · Final Report
              </p>
              <h1 className="text-2xl font-bold">{report.candidate_name}</h1>
              <p className="text-indigo-200 mt-1">{report.selected_role}</p>
              <p className="text-indigo-300 text-xs mt-2">
                {new Date(report.generated_at).toLocaleDateString("en-US", {
                  weekday: "long", year: "numeric", month: "long", day: "numeric",
                })}
              </p>
            </div>

            {/* Overall score circle */}
            <div className="flex flex-col items-center shrink-0">
              <div className="relative w-28 h-28">
                <svg viewBox="0 0 100 100" className="w-full h-full" style={{ transform: "rotate(-90deg)" }}>
                  <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="8" />
                  <circle
                    cx="50" cy="50" r="42"
                    fill="none"
                    stroke="white"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={2 * Math.PI * 42}
                    strokeDashoffset={2 * Math.PI * 42 * (1 - report.overall_score / 100)}
                    style={{ transition: "stroke-dashoffset 1s ease" }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-extrabold tabular-nums leading-none">{report.overall_score}</span>
                  <span className="text-indigo-200 text-[10px] font-medium">/100</span>
                </div>
              </div>
              <p className="text-indigo-200 text-xs font-semibold mt-2 uppercase tracking-wider">Overall</p>
            </div>
          </div>
        </div>

        {/* ── Phase 11: Readiness banner ────────────────────────────────────── */}
        {readiness && (
          <div className={`flex items-start gap-4 border rounded-2xl px-6 py-5 ${readiness.color}`}>
            <div className="shrink-0 w-10 h-10 rounded-full bg-white/60 flex items-center justify-center">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d={readiness.icon} />
              </svg>
            </div>
            <div className="flex-1">
              <p className="font-bold text-base">{readiness.label}</p>
              <p className="text-sm opacity-80 mt-0.5 leading-relaxed">{readiness.desc}</p>
            </div>
            {/* Best-fit roles */}
            {report.best_fit_roles?.length > 0 && (
              <div className="shrink-0 text-right hidden sm:block">
                <p className="text-[10px] font-semibold uppercase tracking-wide opacity-60 mb-1.5">Best-fit Roles</p>
                <div className="flex flex-col gap-1 items-end">
                  {report.best_fit_roles.slice(0, 3).map((role, i) => (
                    <span
                      key={i}
                      className="text-[10px] px-2 py-0.5 rounded-full bg-white/50 font-semibold truncate max-w-[160px]"
                      title={role}
                    >
                      {role}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Behavioral mode banner ────────────────────────────────────────── */}
        {report.behavioral_mode === "placeholder" && (
          <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl px-5 py-3.5">
            <svg className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            <p className="text-xs text-amber-800 leading-relaxed">
              <span className="font-semibold">Behavioral scores are estimated.</span>{" "}
              Communication, Confidence, and Engagement are derived from answer analysis.
              Use the audio recorder in the interview room to get real audio-derived scores.
            </p>
          </div>
        )}
        {report.behavioral_mode === "audio_fallback" && (
          <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl px-5 py-3.5">
            <svg className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
            <p className="text-xs text-blue-800 leading-relaxed">
              <span className="font-semibold">Audio scores included.</span>{" "}
              Install <code className="font-mono bg-blue-100 px-1 rounded">faster-whisper</code> for
              the most accurate transcription-backed scoring.
            </p>
          </div>
        )}
        {report.behavioral_mode === "audio" && (
          <div className="flex items-start gap-3 bg-green-50 border border-green-200 rounded-xl px-5 py-3.5">
            <svg className="w-4 h-4 text-green-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <p className="text-xs text-green-800 leading-relaxed">
              <span className="font-semibold">Whisper audio analysis active.</span>{" "}
              Communication and Confidence derived from real transcription.
            </p>
          </div>
        )}
        {report.behavioral_mode === "video_fallback" && (
          <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl px-5 py-3.5">
            <svg className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
            </svg>
            <p className="text-xs text-blue-800 leading-relaxed">
              <span className="font-semibold">Video scores included.</span>{" "}
              Install <code className="font-mono bg-blue-100 px-1 rounded">opencv-python</code> for
              real face detection and more accurate engagement scores.
            </p>
          </div>
        )}
        {report.behavioral_mode === "video" && (
          <div className="flex items-start gap-3 bg-green-50 border border-green-200 rounded-xl px-5 py-3.5">
            <svg className="w-4 h-4 text-green-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <p className="text-xs text-green-800 leading-relaxed">
              <span className="font-semibold">Computer-vision analysis active.</span>{" "}
              Engagement, Framing, Stability, and Motion derived from real face
              detection on your video captures.
            </p>
          </div>
        )}
        {report.behavioral_mode === "multimodal" && (
          <div className="flex items-start gap-3 bg-indigo-50 border border-indigo-200 rounded-xl px-5 py-3.5">
            <svg className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
            <p className="text-xs text-indigo-800 leading-relaxed">
              <span className="font-semibold">Full multimodal analysis.</span>{" "}
              Audio (Communication, Confidence) and Video (Engagement, Framing, Stability, Motion) scores
              are derived from your recordings — all behavioral axes use real data.
            </p>
          </div>
        )}

        {/* ── Score cards row ───────────────────────────────────────────────── */}
        {(() => {
          const bm            = report.behavioral_mode;
          const hasAudio      = ["audio", "audio_fallback", "multimodal"].includes(bm);
          const hasVideo      = ["video", "video_fallback", "multimodal"].includes(bm);
          const audioReal     = ["audio",  "multimodal"].includes(bm);
          const videoReal     = ["video",  "multimodal"].includes(bm);
          return (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              <ScoreCard label="Technical"    score={report.technical_score}    subtitle="avg of all answers" />
              <ScoreCard label="Communication" score={report.communication_score} subtitle={hasAudio ? (audioReal ? "Whisper clarity" : "audio scoring") : "word-count proxy"} isPlaceholder={!audioReal} />
              <ScoreCard label="Confidence"   score={report.confidence_score}   subtitle={hasAudio ? (audioReal ? "Whisper fluency" : "audio scoring") : "score trajectory"} isPlaceholder={!audioReal} />
              <ScoreCard label="Engagement"   score={report.engagement_score}   subtitle={hasVideo ? (videoReal ? "face detection" : "video scoring") : "session length"} isPlaceholder={!videoReal} />
              <ScoreCard label="Role Fit"     score={report.role_fit_score}     subtitle="resume match" />
            </div>
          );
        })()}

        {/* ── Phase 11: Skill Mastery Map ───────────────────────────────────── */}
        {report.skill_mastery_summary && Object.keys(report.skill_mastery_summary).length > 0 && (
          <SkillMasteryMap
            skillMastery={report.skill_mastery_summary}
          />
        )}

        {/* ── Charts ───────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Radar */}
          <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
              Competency Radar
            </p>
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                <PolarGrid stroke="#e5e7eb" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: "#6b7280", fontSize: 11, fontWeight: 500 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: "#9ca3af", fontSize: 9 }} tickCount={5} />
                <Radar
                  name="Score" dataKey="score"
                  stroke="#6366f1" fill="#6366f1" fillOpacity={0.18}
                  strokeWidth={2} dot={{ r: 3, fill: "#6366f1" }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Per-question bar chart */}
          <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
              Score Breakdown Per Question
            </p>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={barData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }} barCategoryGap="28%">
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "#9ca3af", fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} iconType="circle" iconSize={8} />
                <Bar dataKey="Technical"   fill="#6366f1" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Depth"       fill="#a78bfa" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Correctness" fill="#c4b5fd" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Phase 11: Top strengths with evidence ─────────────────────────── */}
        {report.top_3_strengths_with_evidence?.length > 0 && (
          <ReportSection title="Top Strengths (with Evidence)" icon={<IconStar />}>
            <ul className="space-y-3">
              {report.top_3_strengths_with_evidence.map((s, i) => (
                <li key={i} className="flex items-start gap-3 bg-green-50 border border-green-100 rounded-xl px-4 py-3">
                  <svg className="w-4 h-4 text-green-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  <span className="text-sm text-green-800 leading-relaxed">{s}</span>
                </li>
              ))}
            </ul>
          </ReportSection>
        )}

        {/* ── Strengths (existing, show if no Phase 11 version) ─────────────── */}
        {!report.top_3_strengths_with_evidence?.length && report.strengths.length > 0 && (
          <ReportSection title="Strengths" icon={<IconStar />}>
            <ul className="space-y-2.5">
              {report.strengths.map((s, i) => (
                <li key={i} className="flex items-start gap-3">
                  <svg className="w-4 h-4 text-green-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  <span className="text-sm text-gray-700 leading-relaxed">{s}</span>
                </li>
              ))}
            </ul>
          </ReportSection>
        )}

        {/* ── Phase 11: Top gaps with evidence ──────────────────────────────── */}
        {report.top_3_gaps_with_evidence?.length > 0 && (
          <ReportSection title="Key Gaps (with Evidence)" icon={<IconTarget />}>
            <ul className="space-y-3">
              {report.top_3_gaps_with_evidence.map((gap, i) => (
                <li key={i} className="flex items-start gap-3 bg-orange-50 border border-orange-100 rounded-xl px-4 py-3">
                  <svg className="w-4 h-4 text-orange-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-sm text-orange-800 leading-relaxed">{gap}</span>
                </li>
              ))}
            </ul>
          </ReportSection>
        )}

        {/* ── Improvement areas (existing, show if no Phase 11 version) ─────── */}
        {!report.top_3_gaps_with_evidence?.length && report.improvement_areas.length > 0 && (
          <ReportSection title="Areas to Improve" icon={<IconTarget />}>
            <ul className="space-y-2.5">
              {report.improvement_areas.map((area, i) => (
                <li key={i} className="flex items-start gap-3">
                  <svg className="w-4 h-4 text-orange-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-sm text-gray-700 leading-relaxed">{area}</span>
                </li>
              ))}
            </ul>
          </ReportSection>
        )}

        {/* ── Phase 11: Agent adaptation summary ───────────────────────────── */}
        {report.adaptation_summary?.length > 0 && (
          <ReportSection title="How the AI Adapted to You" icon={<IconBrain />}>
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-3.5 top-3 bottom-3 w-px bg-indigo-100" />
              <div className="space-y-4">
                {report.adaptation_summary.map((step, i) => (
                  <div key={i} className="relative flex gap-4 items-start">
                    <div className="relative z-10 w-7 h-7 rounded-full bg-indigo-100 border-2 border-indigo-200 flex items-center justify-center flex-shrink-0 text-[10px] font-bold text-indigo-600">
                      {i + 1}
                    </div>
                    <div className="flex-1 pt-1 pb-1">
                      <p className="text-sm text-gray-700 leading-relaxed">{step}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </ReportSection>
        )}

        {/* ── Phase 11: 7-day practice plan ────────────────────────────────── */}
        {report.recommended_7_day_plan?.length > 0 && (
          <ReportSection title="7-Day Practice Plan" icon={<IconCalendar />}>
            <div className="space-y-2">
              {report.recommended_7_day_plan.map((task, i) => (
                <div
                  key={i}
                  className="flex items-start gap-4 p-4 bg-gray-50 rounded-xl border border-gray-100 hover:bg-indigo-50 hover:border-indigo-100 transition-colors"
                >
                  <div className="shrink-0 w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center text-xs font-bold text-indigo-600">
                    D{i + 1}
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed pt-1">{task}</p>
                </div>
              ))}
            </div>
          </ReportSection>
        )}

        {/* ── Learning plan (existing) ──────────────────────────────────────── */}
        {report.recommended_learning_plan.length > 0 && (
          <ReportSection title="Personalised Learning Resources" icon={<IconBook />}>
            <div className="space-y-4">
              {report.recommended_learning_plan.map((item, i) => (
                <div key={i} className="flex items-start gap-4 p-4 bg-gray-50 rounded-xl border border-gray-100">
                  <div className="shrink-0 pt-0.5">
                    <span className={`inline-block text-[10px] font-semibold px-2 py-1 rounded-full border uppercase tracking-wide ${priorityStyles[item.priority] ?? priorityStyles.medium}`}>
                      {item.priority}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-0.5">{item.topic}</p>
                    <p className="text-sm font-medium text-gray-800 mb-1">{item.resource}</p>
                    <p className="text-xs text-gray-500 leading-relaxed">{item.reason}</p>
                  </div>
                </div>
              ))}
            </div>
          </ReportSection>
        )}

        {/* ── Final feedback ─────────────────────────────────────────────────── */}
        <ReportSection title="Interviewer Feedback" icon={<IconChat />}>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
            {report.final_feedback}
          </p>
        </ReportSection>

        {/* ── Per-question breakdown ──────────────────────────────────────── */}
        <ReportSection title="Question-by-Question Breakdown" icon={<IconList />}>
          <div className="space-y-5">
            {report.answer_summaries.map((s) => {
              const avg = Math.round((s.technical_score + s.depth_score + s.correctness_score) / 3);
              const avgC = scoreColor(avg);
              const diffCls =
                s.difficulty === "hard"
                  ? "bg-red-50 text-red-600 border-red-200"
                  : s.difficulty === "medium"
                  ? "bg-yellow-50 text-yellow-600 border-yellow-200"
                  : "bg-green-50 text-green-600 border-green-200";

              return (
                <div key={s.question_number} className="border border-gray-100 rounded-xl overflow-hidden">
                  {/* Q header */}
                  <div className="flex items-center justify-between px-5 py-3 bg-gray-50 border-b border-gray-100">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xs font-bold text-gray-400 shrink-0">Q{s.question_number}</span>
                      <span className="text-xs font-medium text-gray-600 truncate">{s.topic}</span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border shrink-0 ${diffCls}`}>
                        {s.difficulty}
                      </span>
                    </div>
                    <span className={`text-xs font-bold tabular-nums shrink-0 ${avgC}`}>{avg}/100</span>
                  </div>

                  <div className="p-5 space-y-4">
                    {/* Adaptation reason */}
                    {s.adaptation_reason && (
                      <div className="flex items-start gap-2 bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2.5">
                        <svg className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round"
                            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <p className="text-xs text-indigo-700">{s.adaptation_reason}</p>
                      </div>
                    )}

                    {/* Question text */}
                    <p className="text-sm text-gray-800 font-medium leading-relaxed">{s.question}</p>

                    {/* Score trio */}
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { label: "Technical",   score: s.technical_score },
                        { label: "Depth",       score: s.depth_score },
                        { label: "Correctness", score: s.correctness_score },
                      ].map(({ label, score }) => (
                        <div key={label} className="text-center">
                          <p className={`text-xl font-extrabold tabular-nums ${scoreColor(score)}`}>{score}</p>
                          <p className="text-[10px] text-gray-400">{label}</p>
                        </div>
                      ))}
                    </div>

                    {/* Audio intelligence panel */}
                    {s.audio_confidence != null && (
                      <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 space-y-2">
                        <p className="text-[10px] font-semibold text-blue-600 uppercase tracking-wider flex items-center gap-1.5">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round"
                              d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                          </svg>
                          Audio Analysis
                        </p>
                        <div className="grid grid-cols-4 gap-2 text-center">
                          {[
                            { label: "Confidence", val: s.audio_confidence, isScore: true },
                            { label: "Clarity",    val: s.audio_clarity,    isScore: true },
                            { label: "Pace",       val: s.audio_speaking_rate ? s.audio_speaking_rate.charAt(0).toUpperCase() + s.audio_speaking_rate.slice(1) : "—", isScore: false },
                            { label: "Pauses",     val: s.audio_pause_count ?? "—", isScore: false },
                          ].map(({ label, val, isScore }) => (
                            <div key={label}>
                              <p className={`text-sm font-bold tabular-nums ${isScore ? scoreColor(val) : "text-gray-700"}`}>
                                {val}
                              </p>
                              <p className="text-[10px] text-gray-400">{label}</p>
                            </div>
                          ))}
                        </div>
                        {s.audio_transcript && (
                          <p className="text-[11px] text-blue-800 leading-relaxed italic border-t border-blue-100 pt-2">
                            "{s.audio_transcript.slice(0, 180)}{s.audio_transcript.length > 180 ? "…" : ""}"
                          </p>
                        )}
                      </div>
                    )}

                    {/* Video intelligence panel */}
                    {s.video_engagement != null && (
                      <div className="bg-violet-50 border border-violet-100 rounded-xl px-4 py-3 space-y-2">
                        <p className="text-[10px] font-semibold text-violet-600 uppercase tracking-wider flex items-center gap-1.5">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round"
                              d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
                          </svg>
                          Video Analysis
                        </p>
                        <div className="grid grid-cols-4 gap-2 text-center">
                          {[
                            { label: "Engagement", val: s.video_engagement, isScore: true },
                            { label: "Framing",    val: s.video_framing,    isScore: true },
                            { label: "Stability",  val: s.video_stability,  isScore: true },
                            { label: "Motion",     val: s.video_movement
                                ? (s.video_movement === "low" ? "Calm"
                                  : s.video_movement === "medium" ? "Moderate"
                                  : "Elevated")
                                : "—",                                        isScore: false },
                          ].map(({ label, val, isScore }) => (
                            <div key={label}>
                              <p className={`text-sm font-bold tabular-nums
                                ${isScore
                                  ? (val != null ? scoreColor(val) : "text-gray-300")
                                  : val === "Calm" ? "text-green-600"
                                  : val === "Moderate" ? "text-yellow-500"
                                  : val === "Elevated" ? "text-red-500"
                                  : "text-gray-400"}`}>
                                {val != null ? val : "—"}
                              </p>
                              <p className="text-[10px] text-gray-400">{label}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Covered / Missing points */}
                    {(s.covered_points.length > 0 || s.missing_points.length > 0) && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-gray-100">
                        {s.covered_points.length > 0 && (
                          <div>
                            <p className="text-[10px] font-semibold text-green-700 uppercase tracking-wider mb-1.5">
                              Covered ({s.covered_points.length})
                            </p>
                            <ul className="space-y-1">
                              {s.covered_points.map((pt, i) => (
                                <li key={i} className="flex items-start gap-1.5 text-xs text-green-800">
                                  <svg className="w-3 h-3 text-green-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                                  </svg>
                                  {pt}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {s.missing_points.length > 0 && (
                          <div>
                            <p className="text-[10px] font-semibold text-orange-600 uppercase tracking-wider mb-1.5">
                              Missing ({s.missing_points.length})
                            </p>
                            <ul className="space-y-1">
                              {s.missing_points.map((pt, i) => (
                                <li key={i} className="flex items-start gap-1.5 text-xs text-orange-800">
                                  <svg className="w-3 h-3 text-orange-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                  </svg>
                                  {pt}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </ReportSection>

        {/* ── Footer actions ────────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-2 pb-4">
          <Link
            to={`/interview/${sessionId}`}
            className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold text-sm hover:bg-indigo-700 transition-colors"
          >
            Continue Interview
          </Link>
          <Link
            to="/roles"
            className="px-6 py-3 bg-white border border-gray-200 text-gray-600 rounded-xl font-semibold text-sm hover:border-gray-300 hover:text-gray-800 transition-colors"
          >
            Try Another Role
          </Link>
          <Link
            to="/upload"
            className="px-6 py-3 bg-white border border-gray-200 text-gray-600 rounded-xl font-semibold text-sm hover:border-gray-300 hover:text-gray-800 transition-colors"
          >
            Upload New Resume
          </Link>
        </div>

      </div>
    </div>
  );
}
