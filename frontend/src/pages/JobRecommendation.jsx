import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import JobCard from "../components/JobCard";
import { getJobRecommendations } from "../services/jobService";

const STATUS = { idle: "idle", loading: "loading", done: "done", error: "error" };

// ── Score bucket helper ───────────────────────────────────────────────────────
function scoreBucket(jobs) {
  const strong   = jobs.filter((j) => j.match_score >= 75).length;
  const good     = jobs.filter((j) => j.match_score >= 50 && j.match_score < 75).length;
  const emerging = jobs.filter((j) => j.match_score < 50).length;
  return { strong, good, emerging };
}

export default function JobRecommendation() {
  const { candidateId: paramId } = useParams();
  const candidateId = paramId || localStorage.getItem("candidate_id");

  const [status, setStatus] = useState(STATUS.idle);
  const [data,   setData]   = useState(null);
  const [error,  setError]  = useState("");

  useEffect(() => {
    if (!candidateId) {
      setError("No candidate ID found. Please upload and analyse your resume first.");
      setStatus(STATUS.error);
      return;
    }
    setStatus(STATUS.loading);
    getJobRecommendations(candidateId)
      .then((d) => { setData(d); setStatus(STATUS.done); })
      .catch((e) => { setError(e.message || "Failed to load job recommendations."); setStatus(STATUS.error); });
  }, [candidateId]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">

      {/* ── Breadcrumb + header ────────────────────────────────────────────── */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-3 flex-wrap">
          <Link to="/upload" className="hover:text-brand-600 transition-colors">
            Resume Upload
          </Link>
          <span>/</span>
          <Link to={`/roles/${candidateId}`} className="hover:text-brand-600 transition-colors">
            Role Recommendations
          </Link>
          <span>/</span>
          <span className="text-gray-700 font-medium">Job Recommendations</span>
        </div>
        <h2 className="text-3xl font-bold text-gray-900 mb-1">Matched Job Openings</h2>
        <p className="text-gray-500">
          Jobs ranked by how closely your skills match each position's requirements.
        </p>
        {candidateId && (
          <p className="text-xs text-gray-400 mt-2 font-mono">Candidate: {candidateId}</p>
        )}
      </div>

      {/* ── Loading ───────────────────────────────────────────────────────── */}
      {status === STATUS.loading && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <svg className="w-8 h-8 animate-spin text-brand-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-gray-500 text-sm">Matching your skills against job listings…</p>
        </div>
      )}

      {/* ── Error ─────────────────────────────────────────────────────────── */}
      {status === STATUS.error && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <div className="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center">
            <svg className="w-7 h-7 text-red-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <p className="text-gray-700 font-medium">{error}</p>
          <Link
            to="/upload"
            className="px-5 py-2.5 bg-brand-500 text-white rounded-xl font-semibold text-sm hover:bg-brand-600 transition-colors"
          >
            Upload Resume
          </Link>
        </div>
      )}

      {/* ── Results ───────────────────────────────────────────────────────── */}
      {status === STATUS.done && data && (
        <>
          {/* Fallback / live data banner */}
          {data.is_live ? (
            <div className="mb-6 flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
              <span className="w-2 h-2 rounded-full bg-green-500 shrink-0 animate-pulse" />
              <p className="text-sm text-green-800">
                <span className="font-semibold">Live job data</span> — these are real current postings matched to your skills.
              </p>
            </div>
          ) : (
            <div className="mb-6 bg-amber-50 border-2 border-amber-300 rounded-xl px-5 py-4">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                </svg>
                <div>
                  <p className="text-sm font-bold text-amber-800">Demo Fallback Data</p>
                  <p className="text-xs text-amber-700 mt-0.5 leading-relaxed">
                    These are sample job listings for demonstration purposes — not current live postings.
                    {data.fallback_reason ? ` ${data.fallback_reason}` : " Configure Adzuna API credentials to see live jobs."}
                  </p>
                </div>
              </div>
            </div>
          )}
          {data.recommended_jobs.length > 0 && (() => {
            const { strong, good, emerging } = scoreBucket(data.recommended_jobs);
            return (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
                <StatCard value={data.recommended_jobs.length} label="Jobs Matched"    color="indigo" />
                <StatCard value={strong}                       label="Strong Fit ≥ 75" color="green"  />
                <StatCard value={good}                         label="Good Fit 50-74"  color="yellow" />
                <StatCard value={data.total_jobs_analyzed}     label="Positions Scanned" color="gray" />
              </div>
            );
          })()}

          {/* Legend */}
          <div className="flex items-center gap-4 mb-6 flex-wrap">
            <span className="text-sm text-gray-500">
              {data.recommended_jobs.length} job
              {data.recommended_jobs.length !== 1 ? "s" : ""} found
            </span>
            <span className="h-1 w-1 rounded-full bg-gray-300" />
            <span className="text-xs text-gray-400">sorted by match score</span>
            <span className="h-1 w-1 rounded-full bg-gray-300" />
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-400 inline-block" /> ≥ 75 Strong
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" /> 50-74 Good
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-orange-400 inline-block" /> &lt; 50 Emerging
              </span>
            </div>
          </div>

          {/* Job grid */}
          {data.recommended_jobs.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-500 text-sm">
                No strong matches found yet. Try adding more skills to your resume.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {data.recommended_jobs.map((job) => (
                <JobCard key={job.job_id} job={job} candidateId={candidateId} />
              ))}
            </div>
          )}

          {/* Footer */}
          <div className="mt-12 pt-8 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-4">
            <Link
              to={`/roles/${candidateId}`}
              className="text-sm text-gray-400 hover:text-brand-600 underline underline-offset-2 transition-colors"
            >
              ← Back to Role Recommendations
            </Link>
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
              </svg>
              Matched against {data.total_jobs_analyzed} positions in our database
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Helper components ─────────────────────────────────────────────────────────

function StatCard({ value, label, color }) {
  const colors = {
    indigo: "bg-indigo-50 border-indigo-100 text-indigo-700",
    green:  "bg-green-50  border-green-100  text-green-700",
    yellow: "bg-yellow-50 border-yellow-100 text-yellow-700",
    gray:   "bg-gray-50   border-gray-100   text-gray-600",
  };
  return (
    <div className={`rounded-2xl border p-4 text-center ${colors[color] ?? colors.gray}`}>
      <p className="text-2xl font-extrabold tabular-nums">{value}</p>
      <p className="text-xs font-medium mt-1 text-gray-500">{label}</p>
    </div>
  );
}
