function ScoreCard({ label, score, subtitle }) {
  const color =
    score >= 70 ? "text-green-600" : score >= 50 ? "text-yellow-500" : "text-orange-500";
  const ring =
    score >= 70 ? "border-green-200 bg-green-50" : score >= 50 ? "border-yellow-200 bg-yellow-50" : "border-orange-200 bg-orange-50";
  const bar =
    score >= 70 ? "bg-green-500" : score >= 50 ? "bg-yellow-400" : "bg-orange-400";

  return (
    <div className={`rounded-xl border p-4 flex flex-col items-center gap-2 ${ring}`}>
      <span className={`text-3xl font-extrabold tabular-nums ${color}`}>{score}</span>
      <div className="w-full bg-white rounded-full h-1.5">
        <div className={`h-1.5 rounded-full transition-all ${bar}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-600">{label}</span>
      {subtitle && <span className="text-[10px] text-gray-400">{subtitle}</span>}
    </div>
  );
}

function PointList({ items, variant }) {
  if (!items?.length) return null;

  const config = {
    covered: {
      icon: (
        <svg className="w-4 h-4 text-green-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      ),
      textCls: "text-green-800",
      label: "Covered",
      headerCls: "text-green-700",
    },
    missing: {
      icon: (
        <svg className="w-4 h-4 text-orange-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
      textCls: "text-orange-800",
      label: "Missing",
      headerCls: "text-orange-600",
    },
  }[variant];

  return (
    <div>
      <p className={`text-xs font-semibold uppercase tracking-wider mb-2 ${config.headerCls}`}>
        {config.label} ({items.length})
      </p>
      <ul className="space-y-1.5">
        {items.map((pt) => (
          <li key={pt} className={`flex items-start gap-2 text-sm ${config.textCls}`}>
            {config.icon}
            {pt}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function EvaluationPanel({ evaluation }) {
  if (!evaluation) return null;

  const { technical_score, depth_score, correctness_score, covered_points, missing_points, feedback } = evaluation;
  const overallLabel = technical_score >= 70 ? "Strong" : technical_score >= 50 ? "Moderate" : "Needs Work";
  const isAi = evaluation.evaluation_mode === "ai";
  const sourceLabel =
    evaluation.evaluation_source_label ||
    (isAi
      ? `AI evaluation (${evaluation.evaluation_provider || "LLM"})`
      : "Rule-based evaluation");
  const sourceClass = isAi
    ? "border-indigo-200 bg-indigo-50 text-indigo-700"
    : "border-gray-200 bg-gray-50 text-gray-600";

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-indigo-50 to-white">
        <div className="flex items-center gap-3 min-w-0">
        <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
          <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-800">Evaluation Complete</p>
          <p className="text-xs text-gray-400">Overall rating: <span className="font-medium text-indigo-600">{overallLabel}</span></p>
        </div>
        </div>
        <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${sourceClass}`}>
          {sourceLabel}
        </span>
      </div>

      <div className="p-6 space-y-6">
        {/* Score cards */}
        <div className="grid grid-cols-3 gap-3">
          <ScoreCard label="Technical" score={technical_score} subtitle="coverage + depth" />
          <ScoreCard label="Depth" score={depth_score} subtitle="detail level" />
          <ScoreCard label="Correctness" score={correctness_score} subtitle="accuracy" />
        </div>

        {/* Covered / Missing */}
        {(covered_points?.length > 0 || missing_points?.length > 0) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-gray-100">
            <PointList items={covered_points} variant="covered" />
            <PointList items={missing_points} variant="missing" />
          </div>
        )}

        {/* Feedback */}
        {feedback && (
          <div className="pt-2 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Interviewer Feedback
            </p>
            <p className="text-sm text-gray-700 leading-relaxed">{feedback}</p>
          </div>
        )}
      </div>
    </div>
  );
}
