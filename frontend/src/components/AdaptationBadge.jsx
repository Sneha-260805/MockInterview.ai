/**
 * AdaptationBadge — shows the AI's reason for choosing the next question.
 * Appears between the evaluation panel and the new question.
 */

const DECISION_DISPLAY = {
  increase_difficulty:     { label: "Difficulty Increased",      color: "text-green-700",  badge: "bg-green-100 text-green-700 border-green-200"  },
  deeper_follow_up:        { label: "Adaptive Follow-Up",        color: "text-blue-700",   badge: "bg-blue-100 text-blue-700 border-blue-200"    },
  strengthen_fundamentals: { label: "Strengthening Fundamentals", color: "text-orange-700", badge: "bg-orange-100 text-orange-700 border-orange-200" },
  confidence_recovery:     { label: "Confidence Recovery",       color: "text-purple-700", badge: "bg-purple-100 text-purple-700 border-purple-200" },
  remediation:             { label: "Remediation",               color: "text-red-700",    badge: "bg-red-100 text-red-700 border-red-200"       },
  final_synthesis:         { label: "Final Synthesis",           color: "text-indigo-700", badge: "bg-indigo-100 text-indigo-700 border-indigo-200" },
  switch_topic:            { label: "Switching Topic",           color: "text-teal-700",   badge: "bg-teal-100 text-teal-700 border-teal-200"    },
  verify_resume_claim:     { label: "Verifying Resume Claim",    color: "text-violet-700", badge: "bg-violet-100 text-violet-700 border-violet-200" },
  behavioral_probe:        { label: "Behavioral Probe",          color: "text-pink-700",   badge: "bg-pink-100 text-pink-700 border-pink-200"    },
};

export default function AdaptationBadge({ reason, questionNumber, maxQuestions, decisionType }) {
  if (!reason) return null;

  const display = decisionType ? (DECISION_DISPLAY[decisionType] || null) : null;

  return (
    <div className="flex items-start gap-3 bg-indigo-50 border border-indigo-200 rounded-2xl px-5 py-4">
      {/* Icon */}
      <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center shrink-0 mt-0.5">
        <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
          />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
          {display ? (
            <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border uppercase tracking-wider ${display.badge}`}>
              {display.label}
            </span>
          ) : (
            <span className="text-xs font-semibold text-indigo-700 uppercase tracking-wider">
              AI Adaptation
            </span>
          )}
          {questionNumber != null && maxQuestions != null && (
            <span className="text-[10px] text-indigo-400 font-medium">
              Question {questionNumber} of {maxQuestions}
            </span>
          )}
        </div>
        <p className="text-sm text-indigo-800 leading-relaxed">{reason}</p>
      </div>
    </div>
  );
}
