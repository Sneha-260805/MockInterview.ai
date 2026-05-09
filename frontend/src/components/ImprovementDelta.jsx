/**
 * ImprovementDelta — shown after a retry evaluation completes.
 *
 * Displays:
 *   - Score before → after for Technical / Depth / Correctness
 *   - Delta badge ("+21 ↑" in green, "-3 ↓" in orange, "±0" in gray)
 *   - "Added N missing concepts" / "Still missing: X, Y"
 *   - Celebration message when improvement ≥ 10 pts
 *
 * Props:
 *   improvedResult  — ImprovedEvaluationResult from /improve-answer
 */

function DeltaBadge({ delta }) {
  if (delta > 0) {
    return (
      <span className="text-xs font-bold text-green-600 flex items-center gap-0.5">
        +{delta}
        <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
        </svg>
      </span>
    );
  }
  if (delta < 0) {
    return (
      <span className="text-xs font-bold text-orange-500 flex items-center gap-0.5">
        {delta}
        <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </span>
    );
  }
  return <span className="text-xs font-bold text-gray-400">±0</span>;
}

function ScoreRow({ label, before, after, delta }) {
  const afterColor = after >= 70 ? "text-green-600" : after >= 50 ? "text-yellow-600" : "text-orange-500";
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-20 shrink-0">{label}</span>
      <span className="text-xs font-semibold text-gray-400 tabular-nums">{before}</span>
      <svg className="w-3 h-3 text-gray-300 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
      </svg>
      <span className={`text-sm font-extrabold tabular-nums ${afterColor}`}>{after}</span>
      <div className="ml-auto">
        <DeltaBadge delta={delta} />
      </div>
    </div>
  );
}

export default function ImprovementDelta({ improvedResult }) {
  if (!improvedResult) return null;

  const {
    technical_score,
    depth_score,
    correctness_score,
    previous_scores = {},
    improvement_delta = {},
    newly_covered = [],
    still_missing = [],
    attempt_number = 2,
    feedback,
  } = improvedResult;

  const techDelta = improvement_delta.technical  ?? 0;
  const depthDelta = improvement_delta.depth     ?? 0;
  const corrDelta  = improvement_delta.correctness ?? 0;

  // Is this a meaningful improvement?
  const netGain = techDelta + depthDelta + corrDelta;
  const isBig   = techDelta >= 10;
  const isAny   = netGain > 0;

  return (
    <div className={`rounded-2xl border overflow-hidden shadow-sm ${
      isBig ? "border-green-200 bg-green-50" : isAny ? "border-indigo-200 bg-indigo-50" : "border-gray-200 bg-gray-50"
    }`}>
      {/* Header */}
      <div className={`flex items-center gap-3 px-5 py-4 border-b ${
        isBig ? "border-green-200 bg-green-100/60" : isAny ? "border-indigo-200 bg-indigo-100/60" : "border-gray-200 bg-gray-100/60"
      }`}>
        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
          isBig ? "bg-green-200" : isAny ? "bg-indigo-200" : "bg-gray-200"
        }`}>
          {isBig ? (
            <svg className="w-4 h-4 text-green-700" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : (
            <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
          )}
        </div>
        <div>
          <p className={`text-sm font-semibold ${isBig ? "text-green-900" : isAny ? "text-indigo-900" : "text-gray-700"}`}>
            {isBig
              ? "Great improvement! 🎉"
              : isAny
              ? "Score updated — keep going"
              : attempt_number >= 3
              ? "Final attempt recorded"
              : "Keep refining your answer"}
          </p>
          <p className={`text-xs ${isBig ? "text-green-700" : isAny ? "text-indigo-600" : "text-gray-500"}`}>
            Attempt {attempt_number} of 3 complete
          </p>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Score comparison */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2.5">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Score Comparison
          </p>
          <ScoreRow
            label="Technical"
            before={previous_scores.technical  ?? "—"}
            after={technical_score}
            delta={techDelta}
          />
          <ScoreRow
            label="Depth"
            before={previous_scores.depth      ?? "—"}
            after={depth_score}
            delta={depthDelta}
          />
          <ScoreRow
            label="Correctness"
            before={previous_scores.correctness ?? "—"}
            after={correctness_score}
            delta={corrDelta}
          />
        </div>

        {/* Concept coverage delta */}
        {(newly_covered.length > 0 || still_missing.length > 0) && (
          <div className="space-y-2.5">
            {newly_covered.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold text-green-700 uppercase tracking-wide mb-1.5">
                  {newly_covered.length === 1
                    ? "1 new concept covered ✓"
                    : `${newly_covered.length} new concepts covered ✓`}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {newly_covered.map((pt) => (
                    <span
                      key={pt}
                      className="text-[10px] px-2 py-0.5 bg-green-100 border border-green-300
                        rounded-full text-green-800 font-medium"
                    >
                      {pt}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {still_missing.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold text-orange-600 uppercase tracking-wide mb-1.5">
                  Still missing:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {still_missing.map((pt) => (
                    <span
                      key={pt}
                      className="text-[10px] px-2 py-0.5 bg-orange-50 border border-orange-200
                        rounded-full text-orange-700"
                    >
                      {pt}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Updated feedback snippet */}
        {feedback && (
          <div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">
              Updated Feedback
            </p>
            <p className="text-xs text-gray-700 leading-relaxed">{feedback}</p>
          </div>
        )}
      </div>
    </div>
  );
}
