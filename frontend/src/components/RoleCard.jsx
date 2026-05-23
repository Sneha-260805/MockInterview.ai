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
    green:  "bg-green-50 text-green-700 border-green-100",
    red:    "bg-red-50 text-red-700 border-red-100",
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

function RoleTypeBadge({ roleType }) {
  if (!roleType) return null;
  const map = {
    realistic:    { label: "Realistic Fit",    cls: "bg-green-100 text-green-700 border-green-200"  },
    stretch:      { label: "Stretch Goal",      cls: "bg-yellow-100 text-yellow-700 border-yellow-200" },
    aspirational: { label: "Aspirational Goal", cls: "bg-orange-100 text-orange-700 border-orange-200" },
  };
  const { label, cls } = map[roleType] || map.realistic;
  return (
    <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border uppercase tracking-wider ${cls}`}>
      {label}
    </span>
  );
}

export default function RoleCard({ role, candidateId }) {
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");
  const [showDetails, setShowDetails] = useState(false);

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
      navigate(`/interview/${session.session_id}`, { state: { session } });
    } catch (err) {
      setStartError(err.message || "Failed to start interview. Please try again.");
      setStarting(false);
    }
  }

  const hasEvidence = role.resume_evidence?.length > 0;
  const hasGaps     = role.gaps?.length > 0;
  const hasWhyFit   = !!role.why_fit;

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md transition-shadow flex flex-col">
      {/* Header */}
      <div className="flex items-start gap-4 px-6 pt-6 pb-4">
        <ScoreRing score={role.match_score} />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h3 className="text-xl font-bold text-gray-900 leading-tight">{role.role}</h3>
            <RoleTypeBadge roleType={role.role_type} />
          </div>
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

      <div className="px-6 pb-4 flex-1 flex flex-col gap-4">

        {/* Reason (legacy — still shown) */}
        <p className="text-sm text-gray-600 leading-relaxed">{role.reason}</p>

        {/* Why this role? — expanded explainability */}
        {hasWhyFit && (
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3">
            <p className="text-[10px] font-bold text-indigo-500 uppercase tracking-wider mb-1">
              Why this role?
            </p>
            <p className="text-xs text-indigo-800 leading-relaxed">{role.why_fit}</p>
          </div>
        )}

        {/* Expand / collapse details button */}
        {(hasEvidence || hasGaps) && (
          <button
            onClick={() => setShowDetails((v) => !v)}
            className="flex items-center gap-2 text-xs font-semibold text-gray-500 hover:text-indigo-600 transition-colors self-start"
          >
            <svg className={`w-3.5 h-3.5 transition-transform ${showDetails ? "rotate-180" : ""}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
            {showDetails ? "Hide" : "Show"} resume evidence & gaps
          </button>
        )}

        {showDetails && (
          <div className="space-y-3">
            {/* Resume evidence */}
            {hasEvidence && (
              <div>
                <p className="text-[10px] font-bold text-green-600 uppercase tracking-wider mb-2">
                  Resume Evidence
                </p>
                <ul className="space-y-1">
                  {role.resume_evidence.map((ev) => (
                    <li key={ev} className="flex items-start gap-2 text-xs text-gray-700">
                      <svg className="w-3 h-3 text-green-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                      {ev}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Gaps */}
            {hasGaps && (
              <div>
                <p className="text-[10px] font-bold text-orange-500 uppercase tracking-wider mb-2">
                  Gaps to Address
                </p>
                <ul className="space-y-1">
                  {role.gaps.map((g) => (
                    <li key={g} className="flex items-start gap-2 text-xs text-gray-700">
                      <svg className="w-3 h-3 text-orange-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                      </svg>
                      {g}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Focus areas */}
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Interview Focus Areas
          </p>
          <TagList items={role.focus_areas} variant="blue" />
        </div>

        {/* Probe areas */}
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Skills to Verify in Interview
          </p>
          <TagList items={role.weak_areas_to_probe} variant="orange" />
        </div>
      </div>

      {/* Error */}
      {startError && (
        <p className="text-xs text-red-600 mx-6 mb-3 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
          {startError}
        </p>
      )}

      {/* CTA */}
      <div className="px-6 pb-6">
        <button
          onClick={handleStart}
          disabled={starting}
          className="w-full py-2.5 rounded-xl font-semibold text-sm transition-colors
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
    </div>
  );
}
