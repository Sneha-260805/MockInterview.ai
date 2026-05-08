/**
 * Phase 11 — SkillMasteryMap
 * Visualises the candidate's evolving skill mastery across interview topics.
 * Each bar represents a topic with a live mastery estimate (0-100).
 */

function MasteryBar({ topic, score }) {
  const color = score >= 70
    ? "bg-green-400"
    : score >= 55
    ? "bg-blue-400"
    : score >= 40
    ? "bg-yellow-400"
    : "bg-red-400";

  const textColor = score >= 70
    ? "text-green-700"
    : score >= 55
    ? "text-blue-700"
    : score >= 40
    ? "text-yellow-700"
    : "text-red-600";

  return (
    <div className="mb-3 last:mb-0">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-gray-600 truncate max-w-[150px]" title={topic}>{topic}</span>
        <span className={`text-xs font-bold tabular-nums ${textColor}`}>{score}</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${Math.max(score, 4)}%` }}
        />
      </div>
    </div>
  );
}

export default function SkillMasteryMap({
  skillMastery = {},
  strongSkills = [],
  weakSkills = [],
  confidenceTrend = "unknown",
  communicationTrend = "unknown",
}) {
  const entries = Object.entries(skillMastery)
    .filter(([topic]) => topic !== "Project Deep Dive")   // hide trivial opener
    .sort(([, a], [, b]) => b - a);                       // highest first

  if (entries.length === 0) return null;

  const trendIcon = {
    improving: { icon: "↑", color: "text-green-600" },
    stable:    { icon: "→", color: "text-yellow-600" },
    declining: { icon: "↓", color: "text-red-500" },
    unknown:   { icon: "?", color: "text-gray-400" },
  };

  const confIcon = trendIcon[confidenceTrend] || trendIcon.unknown;
  const commStyle = {
    good: "text-green-600",
    fair: "text-yellow-600",
    poor: "text-red-500",
    unknown: "text-gray-400",
  }[communicationTrend] || "text-gray-400";

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Skill Mastery</p>
        <span className="text-[10px] text-gray-400">Live estimate</span>
      </div>

      {/* Mastery bars */}
      {entries.map(([topic, score]) => (
        <MasteryBar key={topic} topic={topic} score={score} />
      ))}

      {/* Trend indicators */}
      <div className="mt-4 pt-3 border-t border-gray-100 grid grid-cols-2 gap-3">
        <div className="text-center">
          <p className="text-[10px] text-gray-400 mb-0.5">Confidence</p>
          <p className={`text-sm font-bold ${confIcon.color}`}>
            {confIcon.icon} {confidenceTrend === "unknown" ? "—" : confidenceTrend}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-gray-400 mb-0.5">Communication</p>
          <p className={`text-sm font-bold capitalize ${commStyle}`}>
            {communicationTrend === "unknown" ? "—" : communicationTrend}
          </p>
        </div>
      </div>

      {/* Risk flags */}
    </div>
  );
}

export function CandidateStatePanel({ candidateState }) {
  if (!candidateState) return null;

  const {
    strong_skills = [],
    weak_skills = [],
    skill_mastery = {},
    confidence_trend = "unknown",
    communication_trend = "unknown",
    risk_flags = [],
    inferred_level,
  } = candidateState;

  return (
    <div className="space-y-4">
      <SkillMasteryMap
        skillMastery={skill_mastery}
        strongSkills={strong_skills}
        weakSkills={weak_skills}
        confidenceTrend={confidence_trend}
        communicationTrend={communication_trend}
      />

      {/* Strong/Weak Skills */}
      {(strong_skills.length > 0 || weak_skills.length > 0) && (
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Candidate Profile</p>
          {inferred_level && (
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs text-gray-500">Inferred level:</span>
              <span className="text-xs font-semibold capitalize px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-100">
                {inferred_level}
              </span>
            </div>
          )}
          {strong_skills.length > 0 && (
            <div className="mb-3">
              <p className="text-[10px] text-green-600 font-semibold uppercase tracking-wide mb-1.5">Strong Areas</p>
              <div className="flex flex-wrap gap-1">
                {strong_skills.slice(0, 5).map((s, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 bg-green-50 border border-green-200 rounded-full text-green-700 truncate max-w-[120px]" title={s}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {weak_skills.length > 0 && (
            <div>
              <p className="text-[10px] text-orange-600 font-semibold uppercase tracking-wide mb-1.5">Growth Areas</p>
              <div className="flex flex-wrap gap-1">
                {weak_skills.slice(0, 4).map((s, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 bg-orange-50 border border-orange-200 rounded-full text-orange-700 truncate max-w-[120px]" title={s}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {risk_flags.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <p className="text-[10px] text-red-500 font-semibold uppercase tracking-wide mb-1.5">Risk Flags</p>
              {risk_flags.slice(0, 3).map((flag, i) => (
                <p key={i} className="text-[10px] text-red-600 mb-1 leading-relaxed">⚠ {flag}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
