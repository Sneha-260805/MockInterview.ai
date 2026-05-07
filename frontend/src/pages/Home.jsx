import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import api from "../services/api";

const FEATURES = [
  {
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    title: "Resume Intelligence",
    desc: "Upload PDF or text — AI extracts skills, experience, projects, strengths, and weak areas automatically.",
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    title: "Role & Job Matching",
    desc: "Your skills are scored against 8 engineering roles and 50 job listings to surface the best-fit opportunities.",
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
    title: "Adaptive Interviews",
    desc: "5-question sessions that adjust difficulty in real time based on your performance — always at the right challenge level.",
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
      </svg>
    ),
    title: "Audio Intelligence",
    desc: "Record your spoken answer — Whisper transcription scores your confidence, clarity, speaking pace, and pause frequency.",
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.362a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
    ),
    title: "Video Intelligence",
    desc: "Enable your webcam — face analysis scores engagement, eye contact, posture stability, and stress indicators.",
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    title: "Detailed Feedback Report",
    desc: "Radar chart, per-question bar chart, personalised learning plan, and a full breakdown of every answer.",
  },
];

const STEPS = [
  { num: "1", label: "Upload Resume", desc: "PDF or plain text — we handle the parsing." },
  { num: "2", label: "Practice Interviews", desc: "Adaptive questions tailored to your target role." },
  { num: "3", label: "Get Feedback", desc: "Multimodal report with scores, charts, and a learning plan." },
];

export default function Home() {
  const [apiStatus, setApiStatus] = useState(null);

  useEffect(() => {
    api
      .get("/api/health")
      .then((res) => setApiStatus(res.data))
      .catch(() => setApiStatus({ status: "unreachable" }));
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-br from-brand-50 via-white to-indigo-50">
      {/* ── Hero ── */}
      <section className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-brand-50 border border-brand-500/20 rounded-full text-brand-600 text-xs font-semibold mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
          AI-powered interview preparation
        </div>

        <h1 className="text-5xl sm:text-6xl font-extrabold text-gray-900 leading-tight tracking-tight mb-5">
          Ace your next{" "}
          <span className="text-brand-500 relative">
            interview
            <svg className="absolute -bottom-1 left-0 w-full" viewBox="0 0 200 8" fill="none">
              <path d="M0 6 Q100 0 200 6" stroke="#4f6ef7" strokeWidth="2.5" strokeLinecap="round" fill="none" opacity="0.4"/>
            </svg>
          </span>
        </h1>

        <p className="text-xl text-gray-500 max-w-2xl mx-auto mb-10 leading-relaxed">
          Upload your resume, get matched to the right roles, and practice with adaptive mock
          interviews — complete with audio confidence scoring and video engagement analysis.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            to="/upload"
            className="px-8 py-3.5 bg-brand-500 hover:bg-brand-600 text-white rounded-xl font-semibold text-base transition-colors shadow-md shadow-brand-500/25 hover:shadow-brand-600/30"
          >
            Start Practicing — it's free
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="px-8 py-3.5 border border-gray-200 hover:border-brand-500/50 bg-white hover:bg-brand-50 rounded-xl font-semibold text-gray-600 hover:text-brand-600 text-base transition-all"
          >
            View API Docs →
          </a>
        </div>

        {/* API status */}
        {apiStatus && (
          <p className="mt-6 text-xs text-gray-400 flex items-center justify-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                apiStatus.status === "ok" ? "bg-green-400" : "bg-red-400"
              }`}
            />
            Backend {apiStatus.status === "ok" ? "online" : "offline"}
            {apiStatus.storage && (
              <span className="ml-1 text-gray-300">· {apiStatus.storage} storage</span>
            )}
          </p>
        )}
      </section>

      {/* ── How it works ── */}
      <section className="max-w-4xl mx-auto px-6 pb-16">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-8">
          How it works
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {STEPS.map((step) => (
            <div
              key={step.num}
              className="relative bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-3"
            >
              <div className="w-10 h-10 rounded-xl bg-brand-500 text-white font-bold text-lg flex items-center justify-center shadow-sm">
                {step.num}
              </div>
              <h3 className="font-semibold text-gray-800 text-base">{step.label}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features grid ── */}
      <section className="max-w-5xl mx-auto px-6 pb-24">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-8">
          Everything you need to prepare
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex gap-4 hover:border-brand-500/30 hover:shadow-md transition-all"
            >
              <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-brand-50 text-brand-500 flex items-center justify-center">
                {f.icon}
              </div>
              <div>
                <h3 className="font-semibold text-gray-800 text-sm mb-1">{f.title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA banner ── */}
      <section className="max-w-4xl mx-auto px-6 pb-24">
        <div className="bg-brand-500 rounded-2xl p-10 text-center text-white shadow-lg shadow-brand-500/20">
          <h2 className="text-3xl font-bold mb-3">Ready to start?</h2>
          <p className="text-brand-100 mb-7 text-base">
            Upload your resume and get your first personalised interview question in under a minute.
          </p>
          <Link
            to="/upload"
            className="inline-block px-8 py-3.5 bg-white text-brand-600 hover:bg-brand-50 rounded-xl font-semibold text-base transition-colors shadow-sm"
          >
            Upload Resume →
          </Link>
        </div>
      </section>
    </main>
  );
}
