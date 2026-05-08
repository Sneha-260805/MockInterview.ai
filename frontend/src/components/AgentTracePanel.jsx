/**
 * Phase 11 — AgentTracePanel
 * Shows the decision trace explaining WHY the agent chose the next question.
 * Displayed after clicking "Next Question".
 */

const DECISION_LABELS = {
  increase_difficulty:      { label: "↑ Increasing Difficulty",      color: "text-green-700 bg-green-50 border-green-200" },
  deeper_follow_up:         { label: "→ Deeper Follow-up",           color: "text-blue-700 bg-blue-50 border-blue-200" },
  strengthen_fundamentals:  { label: "↓ Strengthening Fundamentals", color: "text-orange-700 bg-orange-50 border-orange-200" },
  confidence_recovery:      { label: "♡ Confidence Recovery",        color: "text-purple-700 bg-purple-50 border-purple-200" },
  remediation:              { label: "⟳ Remediation",                color: "text-red-700 bg-red-50 border-red-200" },
  final_synthesis:          { label: "★ Final Synthesis",            color: "text-indigo-700 bg-indigo-50 border-indigo-200" },
};

export default function AgentTracePanel({ trace }) {
  if (!trace) return null;

  const style = DECISION_LABELS[trace.decision_type] || {
    label: trace.decision_type,
    color: "text-gray-700 bg-gray-50 border-gray-200",
  };

  return (
    <div className="bg-white border border-indigo-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 bg-indigo-50 border-b border-indigo-100 flex items-center gap-2">
        <svg className="w-4 h-4 text-indigo-500 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
          />
        </svg>
        <span className="text-sm font-semibold text-indigo-700">Agent Decision Trace</span>
      </div>

      <div className="p-5 space-y-4">
        {/* Decision type badge */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className={`text-xs font-bold px-3 py-1 rounded-full border ${style.color}`}>
            {style.label}
          </span>
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className="text-gray-400">Previous topic:</span>
            <span className="font-medium text-gray-700">{trace.previous_topic}</span>
            <span className="text-gray-300 mx-1">·</span>
            <span className="text-gray-400">Score:</span>
            <span className={`font-bold ${
              trace.previous_score >= 70 ? "text-green-600"
              : trace.previous_score >= 50 ? "text-yellow-600"
              : "text-red-500"
            }`}>{trace.previous_score}/100</span>
          </div>
        </div>

        {/* Detected issue */}
        <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">What the agent detected</p>
          <p className="text-xs text-gray-700 leading-relaxed">{trace.detected_issue}</p>
        </div>

        {/* Next question info */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl px-3 py-2.5">
            <p className="text-[10px] text-indigo-400 font-medium mb-0.5">Next Topic</p>
            <p className="text-xs font-semibold text-indigo-800">{trace.next_topic}</p>
          </div>
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl px-3 py-2.5">
            <p className="text-[10px] text-indigo-400 font-medium mb-0.5">Difficulty</p>
            <p className={`text-xs font-semibold capitalize ${
              trace.next_difficulty === "hard" ? "text-red-600"
              : trace.next_difficulty === "medium" ? "text-yellow-600"
              : "text-green-600"
            }`}>{trace.next_difficulty}</p>
          </div>
        </div>

        {/* Evidence bullets */}
        {trace.evidence?.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-2">Evidence</p>
            <ul className="space-y-1">
              {trace.evidence.map((ev, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-gray-600">
                  <span className="mt-0.5 text-indigo-400 font-bold flex-shrink-0">·</span>
                  {ev}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
