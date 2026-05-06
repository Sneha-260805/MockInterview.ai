import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import RoleCard from "../components/RoleCard";
import { getRoles } from "../services/analysisService";

const STATUS = { idle: "idle", loading: "loading", done: "done", error: "error" };

export default function RoleRecommendation() {
  const { candidateId: paramId } = useParams();
  const candidateId = paramId || localStorage.getItem("candidate_id");

  const [status, setStatus] = useState(STATUS.idle);
  const [roles, setRoles] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!candidateId) {
      setStatus(STATUS.error);
      setError("No candidate ID found. Please upload and analyze your resume first.");
      return;
    }
    setStatus(STATUS.loading);
    getRoles(candidateId)
      .then((data) => {
        setRoles(data);
        setStatus(STATUS.done);
      })
      .catch((err) => {
        setError(err.message || "Failed to load role recommendations.");
        setStatus(STATUS.error);
      });
  }, [candidateId]);

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      {/* Page header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-3">
          <Link to="/upload" className="hover:text-brand-600 transition-colors">
            Resume Upload
          </Link>
          <span>/</span>
          <span className="text-gray-700 font-medium">Role Recommendations</span>
        </div>
        <h2 className="text-3xl font-bold text-gray-900 mb-1">Recommended Roles</h2>
        <p className="text-gray-500">
          Based on your resume analysis — roles are ranked by skill match score.
        </p>
        {candidateId && (
          <p className="text-xs text-gray-400 mt-2 font-mono">
            Candidate: {candidateId}
          </p>
        )}
      </div>

      {/* Loading */}
      {status === STATUS.loading && (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <svg className="w-8 h-8 animate-spin text-brand-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-gray-500 text-sm">Generating role recommendations…</p>
        </div>
      )}

      {/* Error */}
      {status === STATUS.error && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <div className="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center">
            <svg className="w-7 h-7 text-red-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
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

      {/* Results */}
      {status === STATUS.done && roles && (
        <>
          <div className="flex items-center gap-3 mb-6">
            <span className="text-sm text-gray-500">
              {roles.recommended_roles.length} role
              {roles.recommended_roles.length !== 1 ? "s" : ""} matched
            </span>
            <span className="h-1 w-1 rounded-full bg-gray-300" />
            <span className="text-xs text-gray-400">sorted by match score</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {roles.recommended_roles.map((role) => (
              <RoleCard key={role.role} role={role} candidateId={candidateId} />
            ))}
          </div>

          <div className="mt-10 pt-8 border-t border-gray-100 flex items-center justify-between">
            <Link
              to="/upload"
              className="text-sm text-gray-400 hover:text-brand-600 underline underline-offset-2 transition-colors"
            >
              ← Upload a different resume
            </Link>
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
              </svg>
              Interview feature arrives in Phase 3
            </div>
          </div>
        </>
      )}
    </div>
  );
}
