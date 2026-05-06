import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startInterview } from "../services/interviewService";

function ScoreRing({ score }) {
  const color =
    score >= 75 ? "text-green-600" : score >= 50 ? "text-yellow-500" : "text-orange-400";
  const bg =
    score >= 75
      ? "bg-green-50 border-green-200"
      : score >= 50
      ? "bg-yellow-50 border-yellow-200"
      : "bg-orange-50 border-orange-200";
  return (
    <div className={`w-16 h-16 rounded-full border-2 flex flex-col items-center justify-center shrink-0 ${bg}`}>
      <span className={`text-xl font-extrabold leading-none ${color}`}>{score}</span>
      <span className="text-[10px] text-gray-400 mt-0.5">/ 100</span>
    </div>
  );
}

function TagList({ items, variant = "blue" }) {
  const styles = {
    blue:   "bg-blue-50 text-blue-700 border-blue-100",
    orange: "bg-orange-50 text-orange-700 border-orange-100",
  };
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className={`text-xs font-medium px-2.5 py-1 rounded-full border ${styles[variant]}`}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

export default function RoleCard({ role, candidateId }) {
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");

  async function handleStart() {
    const id = candidateId || localStorage.getItem("candidate_id");
    if (!id) {
      setStartError("No candidate ID found. Please upload your resume first.");
      return;
    }
    setStarting(true);
    setStartError("");
    try {
      const session = await startInterview(id, role.role);
      localStorage.setItem("session_id", session.session_id);
      // Pass session via router state for instant display (no extra fetch needed)
      navigate(`/interview/${session.session_id}`, { state: { session } });
    } catch (err) {
      setStartError(err.message || "Failed to start interview. Please try again.");
      setStarting(false);
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow flex flex-col">
      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        <ScoreRing score={role.match_score} />
        <div className="flex-1 min-w-0">
          <h3 className="text-xl font-bold text-gray-900">{role.role}</h3>
          <div className="w-full bg-gray-100 rounded-full h-1.5 mt-2">
            <div
              className={`h-1.5 rounded-full transition-all ${
                role.match_score >= 75
                  ? "bg-green-500"
                  : role.match_score >= 50
                  ? "bg-yellow-400"
                  : "bg-orange-400"
              }`}
              style={{ width: `${role.match_score}%` }}
            />
          </div>
        </div>
      </div>

      {/* Reason */}
      <p className="text-sm text-gray-600 mb-5 leading-relaxed">{role.reason}</p>

      {/* Focus areas */}
      <div className="mb-4">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Focus Areas
        </p>
        <TagList items={role.focus_areas} variant="blue" />
      </div>

      {/* Probe areas */}
      <div className="mb-6">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Areas to Probe in Interview
        </p>
        <TagList items={role.weak_areas_to_probe} variant="orange" />
      </div>

      {/* Error */}
      {startError && (
        <p className="text-xs text-red-600 mb-3 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
          {startError}
        </p>
      )}

      {/* CTA — now enabled */}
      <button
        onClick={handleStart}
        disabled={starting}
        className="mt-auto w-full py-2.5 rounded-xl font-semibold text-sm transition-colors
          flex items-center justify-center gap-2
          bg-brand-500 hover:bg-brand-600 text-white
          disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {starting ? (
          <>
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Starting…
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
            Start Interview
          </>
        )}
      </button>
    </div>
  );
}
