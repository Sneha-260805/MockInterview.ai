import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startInterview } from "../services/interviewService";

// ── Score ring ────────────────────────────────────────────────────────────────
function ScoreRing({ score }) {
  const color =
    score >= 80 ? "text-green-600"
    : score >= 72 ? "text-indigo-600"
    : "text-yellow-500";
  const bg =
    score >= 80 ? "bg-green-50 border-green-200"
    : score >= 72 ? "bg-indigo-50 border-indigo-200"
    : "bg-yellow-50 border-yellow-200";
  const bar =
    score >= 80 ? "bg-green-500"
    : score >= 72 ? "bg-indigo-500"
    : "bg-yellow-400";

  return (
    <div className="flex flex-col items-center gap-1 shrink-0">
      <div className={`w-16 h-16 rounded-full border-2 flex flex-col items-center justify-center ${bg}`}>
        <span className={`text-xl font-extrabold leading-none ${color}`}>{score}</span>
        <span className="text-[10px] text-gray-400 mt-0.5">/ 100</span>
      </div>
      <div className="w-16 bg-gray-100 rounded-full h-1">
        <div className={`h-1 rounded-full ${bar}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

// ── Role type badge ───────────────────────────────────────────────────────────
function RoleTypeBadge({ roleType }) {
  if (!roleType) return null;
  const isRealistic = roleType === "realistic";
  return (
    <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${
      isRealistic
        ? "bg-green-100 text-green-700 border-green-200"
        : "bg-amber-100 text-amber-700 border-amber-200"
    }`}>
      {isRealistic ? "✓ Realistic Fit" : "↗ Stretch Opportunity"}
    </span>
  );
}

// ── Rank badge ────────────────────────────────────────────────────────────────
function RankBadge({ rank }) {
  if (!rank || rank > 3) return null;
  const styles = [
    "bg-indigo-100 text-indigo-700 border-indigo-200",
    "bg-green-100 text-green-700 border-green-200",
    "bg-gray-100 text-gray-600 border-gray-200",
  ];
  const labels = ["⭐ Best Match", "#2 Strong Match", "#3 Good Match"];
  return (
    <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${styles[rank - 1]}`}>
      {labels[rank - 1]}
    </span>
  );
}

// ── Small chip ────────────────────────────────────────────────────────────────
function Chip({ text, variant = "blue" }) {
  const styles = {
    blue:   "bg-blue-50 text-blue-700 border-blue-100",
    green:  "bg-green-50 text-green-700 border-green-200",
    amber:  "bg-amber-50 text-amber-700 border-amber-200",
    orange: "bg-orange-50 text-orange-700 border-orange-100",
    gray:   "bg-gray-100 text-gray-600 border-gray-200",
  };
  return (
    <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${styles[variant]}`}>
      {text}
    </span>
  );
}

// ── Evidence list ─────────────────────────────────────────────────────────────
function EvidenceList({ items }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
          <svg
            className="w-4 h-4 text-green-500 shrink-0 mt-0.5"
            fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          {item}
        </li>
      ))}
    </ul>
  );
}

// ── Collapsible section ───────────────────────────────────────────────────────
function Collapsible({ label, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 hover:text-gray-600 transition-colors"
      >
        <svg
          className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        {label}
      </button>
      {open && children}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
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
      navigate(`/interview/${session.session_id}`, { state: { session } });
    } catch (err) {
      setStartError(err.message || "Failed to start interview. Please try again.");
      setStarting(false);
    }
  }

  const isTop = role.rank === 1;
  const ringColor =
    role.match_score >= 80 ? "border-green-200"
    : role.match_score >= 72 ? "border-indigo-200"
    : "border-gray-200";

  return (
    <div className={`bg-white border rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow flex flex-col gap-4
      ${isTop ? `ring-2 ring-indigo-100 ${ringColor}` : "border-gray-200"}`}
    >
      {/* ── Header ── */}
      <div>
        {/* Rank + role type badges */}
        {(role.rank <= 3 || role.role_type) && (
          <div className="flex items-center gap-2 flex-wrap mb-2">
            {role.rank && role.rank <= 3 && <RankBadge rank={role.rank} />}
            {role.role_type && <RoleTypeBadge roleType={role.role_type} />}
          </div>
        )}
        <div className="flex items-start gap-4">
          <ScoreRing score={role.match_score} />
          <div className="flex-1 min-w-0">
            <h3 className="text-xl font-bold text-gray-900 leading-tight">{role.role}</h3>
            <p className="text-sm text-gray-500 mt-1 leading-relaxed">{role.reason}</p>
          </div>
        </div>
      </div>

      {/* ── Why this role? (Gemini explanation) ── */}
      {role.why_fit && role.why_fit !== role.reason && (
        <div className="border-t border-gray-100 pt-3">
          <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-2">
            Why this role?
          </p>
          <div className="flex items-start gap-2 bg-indigo-50 border border-indigo-100 rounded-xl px-3.5 py-3">
            <svg className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <p className="text-sm text-indigo-800 leading-relaxed">{role.why_fit}</p>
          </div>
        </div>
      )}

      {/* ── Resume Evidence ── */}
      {(role.resume_evidence?.length > 0 || role.evidence?.length > 0) && (
        <div className="border-t border-gray-100 pt-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Resume Evidence
          </p>
          <EvidenceList items={role.resume_evidence?.length > 0 ? role.resume_evidence : role.evidence} />
        </div>
      )}

      {/* ── Boosted by / Missing skills ── */}
      {(role.boosted_by?.length > 0 || role.missing_skills?.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-gray-100 pt-3">
          {role.boosted_by?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-green-700 mb-2">Boosted by</p>
              <div className="flex flex-wrap gap-1.5">
                {role.boosted_by.map((b) => (
                  <Chip key={b} text={b} variant="green" />
                ))}
              </div>
            </div>
          )}
          {role.missing_skills?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-amber-700 mb-2">To strengthen fit</p>
              <div className="flex flex-wrap gap-1.5">
                {role.missing_skills.slice(0, 3).map((m) => (
                  <Chip key={m} text={m} variant="amber" />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Skills Gaps (Gemini gaps, else rule-based reduced_by) ── */}
      {(role.gaps?.length > 0 || role.reduced_by?.length > 0) && (
        <div className="bg-orange-50 border border-orange-100 rounded-xl px-4 py-3">
          <p className="text-xs font-semibold text-orange-700 mb-1.5">Skills Gaps</p>
          <ul className="space-y-1">
            {(role.gaps?.length > 0 ? role.gaps : role.reduced_by).map((item, i) => (
              <li key={i} className="text-xs text-orange-800 flex items-start gap-1.5">
                <svg className="w-3.5 h-3.5 text-orange-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Interview prep ── */}
      <div className="border-t border-gray-100 pt-3 space-y-3">
        <Collapsible label="Interview Focus" defaultOpen={isTop}>
          <div className="flex flex-wrap gap-2">
            {(role.interview_focus_areas?.length > 0 ? role.interview_focus_areas : role.focus_areas).map((item) => (
              <Chip key={item} text={item} variant="blue" />
            ))}
          </div>
        </Collapsible>
        {role.what_interview_will_validate?.length > 0 && (
          <Collapsible label="What Interview Will Validate" defaultOpen={isTop}>
            <ul className="space-y-1.5">
              {role.what_interview_will_validate.map((item, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
                  <svg className="w-3 h-3 text-indigo-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </Collapsible>
        )}
        <Collapsible label="Areas to Probe">
          <div className="flex flex-wrap gap-2">
            {role.weak_areas_to_probe.map((item) => (
              <Chip key={item} text={item} variant="orange" />
            ))}
          </div>
        </Collapsible>
      </div>

      {/* ── Error ── */}
      {startError && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
          {startError}
        </p>
      )}

      {/* ── CTA ── */}
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
