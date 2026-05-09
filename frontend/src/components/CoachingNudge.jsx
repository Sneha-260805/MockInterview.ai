/**
 * CoachingNudge — shown before a retry attempt.
 *
 * Displays:
 *   - Missing concepts from the previous attempt
 *   - improvement_hint / interviewer_diagnosis from the evaluation
 *   - Previous score at a glance
 *   - Prefilled answer textarea (controlled by parent)
 *
 * Props:
 *   evaluation        — the EvaluationResult from the first attempt
 *   previousAnswer    — string that prefills the textarea
 *   answer            — controlled textarea value
 *   onAnswerChange    — (newText) => void
 *   onSubmit          — () => void   called when candidate hits "Resubmit"
 *   onCancel          — () => void   collapses the coaching panel back
 *   isSubmitting      — bool
 *   attemptNumber     — int (2 = first retry)
 */
export default function CoachingNudge({
  evaluation,
  answer,
  onAnswerChange,
  onSubmit,
  onCancel,
  isSubmitting,
  attemptNumber = 2,
}) {
  if (!evaluation) return null;

  const { missing_points = [], improvement_hint, interviewer_diagnosis, technical_score } = evaluation;
  const attemptsLeft = 3 - attemptNumber; // max 2 retries (attempt 2 and 3)

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-2xl overflow-hidden shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-amber-200 bg-amber-100/60">
        <div className="w-8 h-8 rounded-full bg-amber-200 flex items-center justify-center shrink-0">
          <svg className="w-4 h-4 text-amber-700" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.355a3.375 3.375 0 01-3 0m3-11.25a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-amber-900">Coaching Mode — Improve Your Answer</p>
          <p className="text-xs text-amber-700">
            Attempt {attemptNumber} of 3
            {attemptsLeft > 0
              ? ` · ${attemptsLeft} retr${attemptsLeft === 1 ? "y" : "ies"} remaining`
              : " · Final attempt"}
          </p>
        </div>
        {/* Previous score badge */}
        <div className="flex flex-col items-end shrink-0">
          <span className="text-[10px] text-amber-600 font-medium">Previous</span>
          <span className={`text-lg font-extrabold tabular-nums ${
            technical_score >= 70 ? "text-green-600"
            : technical_score >= 50 ? "text-yellow-600"
            : "text-orange-600"
          }`}>{technical_score}</span>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Interviewer diagnosis */}
        {interviewer_diagnosis && (
          <div className="bg-white border border-amber-200 rounded-xl px-4 py-3">
            <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide mb-1">
              Interviewer View
            </p>
            <p className="text-sm text-amber-900 leading-relaxed italic">
              "{interviewer_diagnosis}"
            </p>
          </div>
        )}

        {/* Missing concepts */}
        {missing_points.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-amber-800 mb-2">
              Concepts to address this time:
            </p>
            <div className="flex flex-wrap gap-2">
              {missing_points.map((pt) => (
                <span
                  key={pt}
                  className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-white border border-amber-300
                    rounded-full text-amber-800 font-medium"
                >
                  <svg className="w-3 h-3 text-amber-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                  {pt}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Improvement hint */}
        {improvement_hint && (
          <div className="bg-white border border-amber-200 rounded-xl px-4 py-3">
            <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide mb-1">
              How to Improve
            </p>
            <p className="text-xs text-amber-800 leading-relaxed">{improvement_hint}</p>
          </div>
        )}

        {/* Answer textarea — prefilled */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-amber-800">Your improved answer:</p>
            {answer.trim() && (
              <span className="text-[10px] text-amber-600">
                {answer.trim().split(/\s+/).length} words
              </span>
            )}
          </div>
          <textarea
            value={answer}
            onChange={(e) => onAnswerChange(e.target.value)}
            disabled={isSubmitting}
            rows={7}
            placeholder="Edit and expand your previous answer. Target the missing concepts above — use concrete examples and trade-offs."
            className="w-full text-sm text-gray-800 placeholder-gray-400 border border-amber-300 rounded-xl
              px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-amber-400
              focus:border-transparent leading-relaxed transition-shadow bg-white
              disabled:bg-gray-50 disabled:text-gray-500"
          />
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={onSubmit}
            disabled={!answer.trim() || isSubmitting}
            className="flex-1 py-2.5 rounded-xl font-semibold text-white bg-amber-600 hover:bg-amber-700
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors
              flex items-center justify-center gap-2 text-sm"
          >
            {isSubmitting ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Re-evaluating…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                </svg>
                Resubmit Improved Answer
              </>
            )}
          </button>
          <button
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2.5 rounded-xl text-sm font-medium text-amber-700 bg-white border border-amber-300
              hover:bg-amber-50 transition-colors disabled:opacity-40"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
