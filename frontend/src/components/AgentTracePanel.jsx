/**
 * Phase 11 — AgentTracePanel (redesigned for scannability)
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────┐
 *   │ 🧠 AI Adaptive Decision          [badge]        │  ← header
 *   ├─────────────────────────────────────────────────┤
 *   │ Detected: <detected_issue one-liner>            │
 *   │ ✓ <evidence 1>                                  │
 *   │ ⚠ <evidence 2>                                  │
 *   │ ┌─────────────────────────────────────────────┐ │
 *   │ │ ● AI decided                                │ │  ← hero
 *   │ │ <reason_for_adaptation>                     │ │
 *   │ └─────────────────────────────────────────────┘ │
 *   │ [Next: topic]  [difficulty]         Prev: ##/100│
 *   └─────────────────────────────────────────────────┘
 */

const DECISION_LABELS = {
  increase_difficulty:      { label: "↑ Increasing Difficulty",      color: "text-green-700 bg-green-50 border-green-200" },
  deeper_follow_up:         { label: "→ Deeper Follow-up",           color: "text-blue-700 bg-blue-50 border-blue-200" },
  strengthen_fundamentals:  { label: "↓ Strengthening Fundamentals", color: "text-orange-700 bg-orange-50 border-orange-200" },
  confidence_recovery:      { label: "♡ Confidence Recovery",        color: "text-purple-700 bg-purple-50 border-purple-200" },
  remediation:              { label: "⟳ Remediation",                color: "text-red-700 bg-red-50 border-red-200" },
  final_synthesis:          { label: "★ Final Synthesis",            color: "text-indigo-700 bg-indigo-50 border-indigo-200" },
};

/**
 * Classify an evidence string as positive signal or concern.
 * Heuristic: look for positive keywords.
 */
function classifyEvidence(ev) {
  const low = ev.toLowerCase();
  if (
    low.includes("strong") || low.includes("correct") || low.includes("good") ||
    low.includes("clear") || low.includes("confident") || low.includes("high score") ||
    low.includes("above") || low.includes("passed") || low.includes("excellent") ||
    low.includes("demonstrated") || low.includes("showed understanding")
  ) return "positive";
  return "concern";
}

export default function AgentTracePanel({ trace }) {
  if (!trace) return null;

  const style = DECISION_LABELS[trace.decision_type] || {
    label: trace.decision_type,
    color: "text-gray-700 bg-gray-50 border-gray-200",
  };

  // Show up to 3 evidence signals
  const topEvidence = (trace.evidence ?? []).slice(0, 3);

  return (
    <div className="bg-white border border-indigo-200 rounded-2xl shadow-sm overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="px-4 py-3 bg-indigo-50 border-b border-indigo-100 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {/* Brain icon */}
          <svg className="w-3.5 h-3.5 text-indigo-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
          <span className="text-xs font-semibold text-indigo-700">AI Adaptive Decision</span>
        </div>

        {/* Decision type badge — compact, right-aligned */}
        <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border shrink-0 ${style.color}`}>
          {style.label}
        </span>
      </div>

      <div className="p-4 space-y-3">

        {/* ── Detected issue — concise one-liner ─────────────────────────── */}
        {trace.detected_issue && (
          <p className="text-[11px] text-gray-600 leading-relaxed">
            <span className="font-semibold text-gray-800">Detected: </span>
            {trace.detected_issue}
          </p>
        )}

        {/* ── Signal rows — ✓ / ⚠ classified evidence ───────────────────── */}
        {topEvidence.length > 0 && (
          <div className="space-y-1.5">
            {topEvidence.map((ev, i) => {
              const isPositive = classifyEvidence(ev) === "positive";
              return (
                <div key={i} className="flex items-start gap-2">
                  <span className={`text-xs font-bold shrink-0 leading-tight mt-px ${
                    isPositive ? "text-green-500" : "text-amber-500"
                  }`}>
                    {isPositive ? "✓" : "⚠"}
                  </span>
                  <p className="text-[11px] text-gray-600 leading-snug">{ev}</p>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Hero: AI reason box ─────────────────────────────────────────── */}
        {trace.reason_for_adaptation && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-xl px-3.5 py-3">
            <p className="text-[9px] font-bold text-indigo-400 uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse inline-block" />
              AI decided
            </p>
            <p className="text-[12px] text-indigo-900 leading-relaxed font-medium">
              {trace.reason_for_adaptation}
            </p>
          </div>
        )}

        {/* ── Next topic + difficulty + previous score ────────────────────── */}
        <div className="flex items-center gap-2 flex-wrap">
          {trace.next_topic && (
            <span className="text-[10px] font-medium text-gray-600 bg-gray-100 rounded-full px-2.5 py-0.5">
              Next: {trace.next_topic}
            </span>
          )}
          {trace.next_difficulty && (
            <span className={`text-[10px] font-bold rounded-full px-2.5 py-0.5 capitalize ${
              trace.next_difficulty === "hard"   ? "bg-red-100 text-red-700"
              : trace.next_difficulty === "medium" ? "bg-yellow-100 text-yellow-700"
              : "bg-green-100 text-green-700"
            }`}>
              {trace.next_difficulty}
            </span>
          )}
          {trace.previous_score != null && (
            <span className="text-[10px] text-gray-400 ml-auto">
              Prev:{" "}
              <span className={`font-semibold ${
                trace.previous_score >= 70 ? "text-green-600"
                : trace.previous_score >= 50 ? "text-yellow-600"
                : "text-red-500"
              }`}>
                {trace.previous_score}/100
              </span>
            </span>
          )}
        </div>

      </div>
    </div>
  );
}
