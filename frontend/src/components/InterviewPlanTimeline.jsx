/**
 * Phase 11 — InterviewPlanTimeline
 * Shows the agent's personalised interview plan as a vertical timeline.
 * Each step reveals the topic, difficulty, reason, and resume evidence.
 */

const DIFF_STYLE = {
  easy:   "bg-green-50 text-green-700 border-green-200",
  medium: "bg-yellow-50 text-yellow-700 border-yellow-200",
  hard:   "bg-red-50   text-red-700   border-red-200",
};

const DIFF_DOT = {
  easy:   "bg-green-400",
  medium: "bg-yellow-400",
  hard:   "bg-red-400",
};

export default function InterviewPlanTimeline({ plan = [], currentStep = 1, agentSummary = "" }) {
  if (!plan || plan.length === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 bg-indigo-50 border-b border-indigo-100 flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center flex-shrink-0 mt-0.5">
          <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z"
            />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-indigo-800">Personalised Interview Plan</p>
          {agentSummary && (
            <p className="text-xs text-indigo-600 mt-0.5 leading-relaxed">{agentSummary}</p>
          )}
        </div>
      </div>

      {/* Timeline */}
      <div className="p-5">
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-3.5 top-4 bottom-4 w-px bg-gray-200" />

          <div className="space-y-5">
            {plan.map((item, idx) => {
              const step = idx + 1;
              const isActive = step === currentStep;
              const isDone = step < currentStep;
              const isFuture = step > currentStep;

              return (
                <div key={idx} className="relative flex gap-4">
                  {/* Step dot */}
                  <div className={`relative z-10 w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold border-2
                    ${isDone
                      ? "bg-green-500 border-green-500 text-white"
                      : isActive
                      ? "bg-indigo-500 border-indigo-500 text-white shadow-md shadow-indigo-200"
                      : "bg-white border-gray-300 text-gray-400"
                    }`}
                  >
                    {isDone ? (
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    ) : step}
                  </div>

                  {/* Content */}
                  <div className={`flex-1 pb-1 ${isFuture ? "opacity-60" : ""}`}>
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`text-sm font-semibold ${isActive ? "text-indigo-700" : "text-gray-800"}`}>
                        {item.topic}
                      </span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border capitalize
                        ${DIFF_STYLE[item.difficulty] || DIFF_STYLE.medium}`}>
                        {item.difficulty}
                      </span>
                      {isActive && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-600">
                          Current
                        </span>
                      )}
                    </div>

                    {/* Reason */}
                    <p className="text-xs text-gray-500 leading-relaxed mb-1.5">{item.reason}</p>

                    {/* Resume evidence */}
                    {item.linked_resume_evidence?.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {item.linked_resume_evidence.map((ev, ei) => (
                          <span
                            key={ei}
                            className="text-[10px] px-2 py-0.5 bg-gray-50 border border-gray-200 rounded-full text-gray-500 truncate max-w-[200px]"
                            title={ev}
                          >
                            {ev}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
