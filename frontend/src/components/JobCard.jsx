import { useNavigate } from "react-router-dom";

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(s) {
  return s >= 75 ? "text-green-600" : s >= 50 ? "text-yellow-500" : "text-orange-400";
}
function scoreBg(s) {
  return s >= 75
    ? "bg-green-50 border-green-200"
    : s >= 50
    ? "bg-yellow-50 border-yellow-200"
    : "bg-orange-50 border-orange-200";
}

/**
 * Map a job title to the closest mock-interview role available in the system.
 */
function mapToInterviewRole(title) {
  const t = title.toLowerCase();
  if (t.includes("full stack") || t.includes("fullstack") || t.includes("mern"))
    return "Full Stack Developer";
  if (t.includes("frontend") || t.includes("front-end") || t.includes("react") || t.includes("ui engineer") || t.includes("vue") || t.includes("angular"))
    return "Frontend Developer";
  if (t.includes("backend") || t.includes("back-end") || t.includes("node.js") || t.includes("django") || t.includes("fastapi") || t.includes("spring"))
    return "Backend Developer";
  if (t.includes("data scientist") || t.includes("data science") || t.includes("nlp data"))
    return "Data Scientist";
  if (t.includes("machine learning") || t.includes("ml engineer") || t.includes("ai engineer") || t.includes("mlops") || t.includes("llm") || t.includes("deep learning") || t.includes("research engineer"))
    return "ML / AI Engineer";
  if (t.includes("devops") || t.includes("cloud") || t.includes("sre") || t.includes("reliability") || t.includes("infrastructure") || t.includes("platform engineer"))
    return "DevOps / Cloud Engineer";
  if (t.includes("mobile") || t.includes("react native") || t.includes("ios") || t.includes("android") || t.includes("flutter"))
    return "Mobile Developer";
  if (t.includes("data engineer") || t.includes("analytics engineer") || t.includes("kafka") || t.includes("streaming"))
    return "Data Engineer";
  return null;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SkillChip({ label, variant }) {
  const styles =
    variant === "matched"
      ? "bg-green-50 text-green-700 border-green-200"
      : "bg-orange-50 text-orange-700 border-orange-200";
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border ${styles}`}>
      {variant === "matched" ? (
        <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      ) : (
        <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
      )}
      {label}
    </span>
  );
}

function LiveBadge({ isLive }) {
  if (isLive) {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-50 border border-green-200 text-green-700 uppercase tracking-wider">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse inline-block" />
        Live Posting
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 border border-gray-200 text-gray-500 uppercase tracking-wider">
      Sample Job
    </span>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function JobCard({ job, candidateId }) {
  const navigate = useNavigate();
  const interviewRole = mapToInterviewRole(job.title);

  function handlePractice() {
    if (interviewRole) {
      navigate(`/roles/${candidateId}`, {
        state: { highlightRole: interviewRole },
      });
    } else {
      navigate(`/roles/${candidateId}`);
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md transition-shadow flex flex-col overflow-hidden">

      {/* ── Header strip ─────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3 px-6 pt-6 pb-4 border-b border-gray-100">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-0.5">
            <h3 className="text-base font-bold text-gray-900 leading-snug">{job.title}</h3>
            <LiveBadge isLive={job.is_live} />
          </div>
          <p className="text-sm font-medium text-brand-600">{job.company}</p>

          {/* Location + experience */}
          <div className="flex items-center flex-wrap gap-2 mt-2">
            <span className="inline-flex items-center gap-1 text-xs text-gray-500">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
              </svg>
              {job.location}
            </span>
            <span className="text-gray-300">·</span>
            <span className="inline-flex items-center gap-1 text-xs text-gray-500">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0M12 12.75h.008v.008H12v-.008z" />
              </svg>
              {job.experience}
            </span>
          </div>
        </div>

        {/* Match score circle */}
        <div className={`w-14 h-14 rounded-full border-2 flex flex-col items-center justify-center shrink-0 ${scoreBg(job.match_score)}`}>
          <span className={`text-lg font-extrabold leading-none ${scoreColor(job.match_score)}`}>
            {job.match_score}
          </span>
          <span className="text-[9px] text-gray-400 leading-none mt-0.5">/ 100</span>
        </div>
      </div>

      <div className="px-6 py-4 flex-1 flex flex-col gap-4">

        {/* ── Description ──────────────────────────────────────────────────── */}
        <p className="text-sm text-gray-600 leading-relaxed line-clamp-2">{job.description}</p>

        {/* ── Why this job fits ─────────────────────────────────────────────── */}
        <div className="flex items-start gap-2 bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3">
          <svg className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <div>
            <p className="text-[10px] font-bold text-indigo-500 uppercase tracking-wider mb-0.5">
              Why this job fits
            </p>
            <p className="text-xs text-indigo-800 leading-relaxed">{job.why_fit}</p>
          </div>
        </div>

        {/* ── Skills ───────────────────────────────────────────────────────── */}
        <div className="space-y-2.5">
          {job.matched_skills.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                You have ({job.matched_skills.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {job.matched_skills.map((s) => (
                  <SkillChip key={s} label={s} variant="matched" />
                ))}
              </div>
            </div>
          )}
          {job.missing_skills.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                To develop ({job.missing_skills.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {job.missing_skills.map((s) => (
                  <SkillChip key={s} label={s} variant="missing" />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Application readiness ─────────────────────────────────────────── */}
        {job.application_readiness && (
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3">
            <svg className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
            </svg>
            <div>
              <p className="text-[10px] font-bold text-amber-600 uppercase tracking-wider mb-0.5">
                Recommended preparation
              </p>
              <p className="text-xs text-amber-800 leading-relaxed">{job.application_readiness}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Footer CTA ───────────────────────────────────────────────────── */}
      <div className="px-6 pb-6 flex flex-col gap-2">
        {/* Apply button (shown when apply_url is available) */}
        {job.apply_url && (
          <a
            href={job.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full py-2.5 rounded-xl font-semibold text-sm transition-colors
              flex items-center justify-center gap-2
              bg-green-600 hover:bg-green-700 text-white"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
            </svg>
            Apply Now
          </a>
        )}

        {/* Practice interview */}
        <button
          onClick={handlePractice}
          className="w-full py-2.5 rounded-xl font-semibold text-sm transition-colors
            flex items-center justify-center gap-2
            bg-brand-500 hover:bg-brand-600 text-white"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
          </svg>
          {interviewRole ? `Practice for ${interviewRole}` : "Practice Interview"}
        </button>
      </div>
    </div>
  );
}
