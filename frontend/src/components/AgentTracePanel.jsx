/**
 * AgentTracePanel
 *
 * Displays the interview agent's reasoning in a structured, readable format.
 * Makes it immediately visible to judges that the system is adaptive and explainable —
 * not just a static question bank.
 *
 * Props:
 *   evaluation      – current answer evaluation (technical_score, depth_score,
 *                     correctness_score, missing_points, feedback)
 *   adaptationReason – plain-English reason string returned by the backend
 *   prevQuestion     – the question that was just answered (topic, difficulty)
 *   nextQuestion     – the question that was selected next (topic, difficulty)
 *   confidenceScore  – derived confidence score (0-100)
 */
export default function AgentTracePanel({
  evaluation,
  adaptationReason,
  prevQuestion,
  nextQuestion,
  confidenceScore,
}) {
  if (!evaluation || !adaptationReason) return null;

  const tech   = evaluation.technical_score ?? 0;
  const depth  = evaluation.depth_score ?? 0;
  const correct = evaluation.correctness_score ?? 0;
  const avg    = Math.round((tech + depth + correct) / 3);
  const missing = evaluation.missing_points ?? [];

  // Derive observation label from scores
  const observation = _buildObservation(avg, tech, depth, correct, prevQuestion, missing);
  const decision    = _buildDecision(adaptationReason, nextQuestion);
  const nextAction  = _buildNextAction(nextQuestion);

  return (
    <div className="bg-white border border-violet-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-3.5 bg-gradient-to-r from-violet-50 to-white border-b border-violet-100">
        <div className="w-7 h-7 rounded-full bg-violet-100 flex items-center justify-center shrink-0">
          {/* Brain / agent icon */}
          <svg className="w-4 h-4 text-violet-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3
                 m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547
                 A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531
                 c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <div>
          <p className="text-xs font-bold text-violet-700 uppercase tracking-wider">Agent Decision Trace</p>
          <p className="text-[10px] text-violet-400">Why the agent chose the next question</p>
        </div>
        {/* Live badge */}
        <span className="ml-auto flex items-center gap-1 text-[10px] font-semibold text-violet-600 bg-violet-50 border border-violet-200 px-2 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse inline-block" />
          Adaptive AI
        </span>
      </div>

      <div className="p-5 space-y-4">

        {/* ── Row 1: Observation ───────────────────────────────────────────── */}
        <TraceRow
          step="1"
          label="Agent Observed"
          color="blue"
          icon={<EyeIcon />}
        >
          <p className="text-sm text-blue-900 leading-relaxed">{observation}</p>
        </TraceRow>

        {/* ── Row 2: Evidence (scores + missing) ──────────────────────────── */}
        <TraceRow
          step="2"
          label="Evidence"
          color="gray"
          icon={<ChartIcon />}
        >
          <div className="flex flex-wrap gap-4 mb-2">
            <ScorePill label="Technical"    score={tech}    />
            <ScorePill label="Depth"        score={depth}   />
            <ScorePill label="Correctness"  score={correct} />
            {confidenceScore != null && (
              <ScorePill label="Confidence" score={confidenceScore} />
            )}
          </div>
          {missing.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">
                Missing concepts ({missing.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {missing.map((pt) => (
                  <span key={pt} className="text-[11px] bg-orange-50 border border-orange-200 text-orange-700 rounded-full px-2 py-0.5">
                    {pt}
                  </span>
                ))}
              </div>
            </div>
          )}
        </TraceRow>

        {/* ── Row 3: Decision ─────────────────────────────────────────────── */}
        <TraceRow
          step="3"
          label="Agent Decision"
          color="violet"
          icon={<BrainIcon />}
        >
          <p className="text-sm text-violet-900 leading-relaxed font-medium">{decision}</p>
        </TraceRow>

        {/* ── Row 4: Why ──────────────────────────────────────────────────── */}
        <TraceRow
          step="4"
          label="Why"
          color="indigo"
          icon={<LightbulbIcon />}
        >
          <p className="text-sm text-indigo-900 leading-relaxed">{adaptationReason}</p>
        </TraceRow>

        {/* ── Row 5: Next action ───────────────────────────────────────────── */}
        {nextAction && (
          <TraceRow
            step="5"
            label="Next Action"
            color="green"
            icon={<ArrowIcon />}
          >
            <p className="text-sm text-green-900 leading-relaxed">{nextAction}</p>
          </TraceRow>
        )}
      </div>
    </div>
  );
}

// ── Helper builders ───────────────────────────────────────────────────────────

function _buildObservation(avg, tech, depth, correct, prevQuestion, missing) {
  const topic = prevQuestion?.topic ?? "the previous question";
  if (avg >= 80) {
    return `Strong answer on "${topic}" (average ${avg}/100). Technical depth and correctness were both high — candidate shows confident mastery of this concept.`;
  }
  if (avg >= 60) {
    return `Solid answer on "${topic}" (average ${avg}/100). Core concepts addressed but ${missing.length > 0 ? `${missing.length} expected point(s) were missed` : "depth could be improved"}.`;
  }
  if (avg >= 40) {
    return `Moderate answer on "${topic}" (average ${avg}/100). Answer showed partial understanding — ${missing.length > 0 ? `missing: ${missing.slice(0, 2).join(", ")}` : "key concepts were not fully developed"}.`;
  }
  return `Weak answer on "${topic}" (average ${avg}/100). Fundamental concepts were not clearly articulated — ${missing.length > 0 ? `missing: ${missing.slice(0, 3).join(", ")}` : "significant gaps detected"}.`;
}

function _buildDecision(reason, nextQ) {
  if (!nextQ) return reason;
  const diff = nextQ.difficulty ?? "medium";
  const topic = nextQ.topic ?? "next topic";
  const diffLabel = { easy: "simpler", medium: "intermediate", hard: "advanced" }[diff] ?? diff;
  return `Ask a ${diffLabel} question on "${topic}".`;
}

function _buildNextAction(nextQ) {
  if (!nextQ) return null;
  const diff = nextQ.difficulty ?? "medium";
  const topic = nextQ.topic ?? "next topic";
  const diffLabel = { easy: "an easier foundational", medium: "an intermediate", hard: "a challenging advanced" }[diff] ?? "a";
  return `Generate ${diffLabel} question on "${topic}" to ${
    diff === "easy"   ? "rebuild confidence and check fundamentals" :
    diff === "hard"   ? "challenge breadth and system-level thinking" :
                        "assess solid understanding and edge-case awareness"
  }.`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

const COLOR_MAP = {
  blue:   { bg: "bg-blue-50",   border: "border-blue-100",   num: "bg-blue-100 text-blue-700",   label: "text-blue-500"   },
  gray:   { bg: "bg-gray-50",   border: "border-gray-100",   num: "bg-gray-100 text-gray-600",   label: "text-gray-400"   },
  violet: { bg: "bg-violet-50", border: "border-violet-100", num: "bg-violet-100 text-violet-700", label: "text-violet-500" },
  indigo: { bg: "bg-indigo-50", border: "border-indigo-100", num: "bg-indigo-100 text-indigo-700", label: "text-indigo-500" },
  green:  { bg: "bg-green-50",  border: "border-green-100",  num: "bg-green-100 text-green-700",  label: "text-green-500"  },
};

function TraceRow({ step, label, color, icon, children }) {
  const c = COLOR_MAP[color] ?? COLOR_MAP.gray;
  return (
    <div className={`rounded-xl border ${c.border} ${c.bg} p-4`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${c.num}`}>
          {step}
        </span>
        <span className="w-3.5 h-3.5 shrink-0 text-current" style={{ color: "inherit" }}>{icon}</span>
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${c.label}`}>{label}</span>
      </div>
      {children}
    </div>
  );
}

function ScorePill({ label, score }) {
  const color =
    score >= 70 ? "text-green-700 bg-green-50 border-green-200" :
    score >= 50 ? "text-yellow-700 bg-yellow-50 border-yellow-200" :
                  "text-orange-700 bg-orange-50 border-orange-200";
  return (
    <div className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${color}`}>
      <span>{label}</span>
      <span className="tabular-nums">{score}</span>
    </div>
  );
}

// ── SVG icons (inline, no external dep) ──────────────────────────────────────

function EyeIcon() {
  return (
    <svg fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" className="w-3.5 h-3.5 text-blue-500">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" className="w-3.5 h-3.5 text-gray-400">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" className="w-3.5 h-3.5 text-violet-500">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3
           m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547
           A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531
           c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  );
}

function LightbulbIcon() {
  return (
    <svg fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" className="w-3.5 h-3.5 text-indigo-500">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3
           m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547
           A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531
           c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" className="w-3.5 h-3.5 text-green-500">
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
    </svg>
  );
}
