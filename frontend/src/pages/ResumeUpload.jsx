import { useState } from "react";
import { Link } from "react-router-dom";
import UploadBox from "../components/UploadBox";
import { uploadResume } from "../services/resumeService";
import { analyzeResume } from "../services/analysisService";

const S = { idle: "idle", loading: "loading", done: "done", error: "error" };

export default function ResumeUpload() {
  const [file, setFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(S.idle);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadError, setUploadError] = useState("");

  const [analyzeStatus, setAnalyzeStatus] = useState(S.idle);
  const [analysis, setAnalysis] = useState(null);
  const [roles, setRoles] = useState(null);
  const [analyzeError, setAnalyzeError] = useState("");

  async function handleUpload() {
    if (!file) return;
    setUploadStatus(S.loading);
    setUploadError("");
    setUploadResult(null);
    setAnalysis(null);
    setRoles(null);
    setAnalyzeStatus(S.idle);

    try {
      const data = await uploadResume(file);
      localStorage.setItem("candidate_id", data.candidate_id);
      setUploadResult(data);
      setUploadStatus(S.done);
    } catch (err) {
      setUploadError(err.message || "Upload failed. Please try again.");
      setUploadStatus(S.error);
    }
  }

  async function handleAnalyze() {
    if (!uploadResult) return;
    setAnalyzeStatus(S.loading);
    setAnalyzeError("");

    try {
      const data = await analyzeResume(uploadResult.candidate_id, uploadResult.raw_text);
      setAnalysis(data.analysis);
      setRoles(data.roles);
      setAnalyzeStatus(S.done);
    } catch (err) {
      setAnalyzeError(err.message || "Analysis failed. Please try again.");
      setAnalyzeStatus(S.error);
    }
  }

  function handleReset() {
    setFile(null);
    setUploadStatus(S.idle);
    setUploadResult(null);
    setUploadError("");
    setAnalysis(null);
    setRoles(null);
    setAnalyzeStatus(S.idle);
    setAnalyzeError("");
  }

  const uploading = uploadStatus === S.loading;
  const analyzing = analyzeStatus === S.loading;

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <h2 className="text-3xl font-bold text-gray-900 mb-1">Upload Resume</h2>
      <p className="text-gray-500 mb-8">
        Upload your PDF or TXT resume. We'll extract the text, analyse your skills, and recommend interview roles.
      </p>

      {/* ── Step 1: Upload ─────────────────────────────────────── */}
      <div className="space-y-4">
        <UploadBox
          onFileSelect={setFile}
          disabled={uploading || uploadStatus === S.done}
        />

        {uploadStatus === S.error && <ErrorBanner message={uploadError} />}

        {uploadStatus !== S.done && (
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="w-full py-3 rounded-xl font-semibold text-white bg-brand-500 hover:bg-brand-600
              disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {uploading ? <Spinner label="Extracting text…" /> : "Extract Resume Text"}
          </button>
        )}
      </div>

      {/* ── After upload ───────────────────────────────────────── */}
      {uploadStatus === S.done && uploadResult && (
        <div className="mt-8 space-y-6">
          <SuccessBanner candidateId={uploadResult.candidate_id} fileName={uploadResult.file_name} />
          <TextPreview text={uploadResult.raw_text} />

          {/* ── Step 2: Analyse ──────────────────────────────────── */}
          {analyzeStatus === S.idle && (
            <button
              onClick={handleAnalyze}
              className="w-full py-3 rounded-xl font-semibold text-white bg-indigo-600 hover:bg-indigo-700
                transition-colors flex items-center justify-center gap-2"
            >
              Analyse Resume & Recommend Roles →
            </button>
          )}

          {analyzeStatus === S.loading && (
            <div className="flex items-center justify-center gap-3 py-6 text-indigo-600">
              <Spinner />
              <span className="text-sm font-medium">Analysing skills and generating role recommendations…</span>
            </div>
          )}

          {analyzeStatus === S.error && <ErrorBanner message={analyzeError} />}

          {/* ── Step 3: Show analysis ─────────────────────────────── */}
          {analyzeStatus === S.done && analysis && (
            <AnalysisPanel analysis={analysis} roles={roles} />
          )}

          <button
            onClick={handleReset}
            className="text-sm text-gray-400 hover:text-brand-600 underline underline-offset-2 transition-colors"
          >
            Upload a different resume
          </button>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function Spinner({ label }) {
  return (
    <>
      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
      {label && <span>{label}</span>}
    </>
  );
}

function ErrorBanner({ message }) {
  return (
    <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
      <svg className="w-5 h-5 mt-0.5 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      <span>{message}</span>
    </div>
  );
}

function SuccessBanner({ candidateId, fileName }) {
  return (
    <div className="flex items-start gap-4 bg-green-50 border border-green-200 rounded-2xl px-5 py-4">
      <div className="w-9 h-9 rounded-full bg-green-100 flex items-center justify-center shrink-0">
        <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      </div>
      <div>
        <p className="font-semibold text-green-800 text-sm">Resume uploaded successfully</p>
        <p className="text-xs text-green-600 mt-0.5 font-mono break-all">{fileName}</p>
        <p className="text-xs text-gray-400 mt-1">
          Candidate ID: <span className="font-mono text-gray-600">{candidateId}</span>
        </p>
      </div>
    </div>
  );
}

function TextPreview({ text }) {
  const words = text.trim().split(/\s+/).length;
  return (
    <div className="border border-gray-200 rounded-2xl overflow-hidden bg-white shadow-sm">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-gray-50">
        <span className="text-sm font-semibold text-gray-700">Extracted Text Preview</span>
        <span className="text-xs text-gray-400">{words.toLocaleString()} words</span>
      </div>
      <pre className="text-xs text-gray-700 font-mono leading-relaxed p-5 overflow-y-auto max-h-56 whitespace-pre-wrap break-words">
        {text}
      </pre>
    </div>
  );
}

function Tag({ label, variant = "blue" }) {
  const styles = {
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    green: "bg-green-50 text-green-700 border-green-100",
    purple: "bg-purple-50 text-purple-700 border-purple-100",
    gray: "bg-gray-100 text-gray-600 border-gray-200",
  };
  return (
    <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${styles[variant]}`}>
      {label}
    </span>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{title}</p>
      {children}
    </div>
  );
}

function LevelBadge({ level }) {
  const map = {
    junior: { label: "Junior", cls: "bg-blue-100 text-blue-700" },
    mid: { label: "Mid-level", cls: "bg-yellow-100 text-yellow-700" },
    senior: { label: "Senior", cls: "bg-green-100 text-green-700" },
  };
  const { label, cls } = map[level] || { label: level, cls: "bg-gray-100 text-gray-600" };
  return (
    <span className={`text-xs font-semibold px-3 py-1 rounded-full ${cls}`}>{label}</span>
  );
}

function AnalysisPanel({ analysis, roles }) {
  return (
    <div className="border border-indigo-100 rounded-2xl overflow-hidden bg-white shadow-sm">
      {/* Header */}
      <div className="bg-indigo-50 px-6 py-4 border-b border-indigo-100 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-gray-900">
            {analysis.candidate_name || "Candidate"}
          </h3>
          <div className="flex gap-4 mt-1 text-xs text-gray-500">
            {analysis.email && <span>{analysis.email}</span>}
            {analysis.phone && <span>{analysis.phone}</span>}
          </div>
        </div>
        <LevelBadge level={analysis.experience_level} />
      </div>

      <div className="p-6 space-y-6">
        {/* Domains */}
        {analysis.domains?.length > 0 && (
          <Section title="Domains">
            <div className="flex flex-wrap gap-2">
              {analysis.domains.map((d) => <Tag key={d} label={d} variant="purple" />)}
            </div>
          </Section>
        )}

        {/* Skills */}
        {analysis.skills?.length > 0 && (
          <Section title={`Skills (${analysis.skills.length} detected)`}>
            <div className="flex flex-wrap gap-2">
              {analysis.skills.map((s) => <Tag key={s} label={s} variant="blue" />)}
            </div>
          </Section>
        )}

        {/* Education */}
        {analysis.education && (
          <Section title="Education">
            <p className="text-sm text-gray-700">{analysis.education}</p>
          </Section>
        )}

        {/* Projects */}
        {analysis.projects?.length > 0 && (
          <Section title={`Projects (${analysis.projects.length} found)`}>
            <div className="space-y-3">
              {analysis.projects.map((p) => (
                <div key={p.name} className="bg-gray-50 rounded-xl px-4 py-3">
                  <p className="font-semibold text-sm text-gray-800">{p.name}</p>
                  {p.summary && (
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">{p.summary}</p>
                  )}
                  {p.technologies?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {p.technologies.map((t) => <Tag key={t} label={t} variant="gray" />)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Strengths */}
        {analysis.strengths?.length > 0 && (
          <Section title="Strengths">
            <ul className="space-y-1.5">
              {analysis.strengths.map((s) => (
                <li key={s} className="flex items-start gap-2 text-sm text-gray-700">
                  <span className="text-green-500 mt-0.5">✓</span> {s}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {/* Weak areas */}
        {analysis.weak_areas?.length > 0 && (
          <Section title="Areas to Develop">
            <ul className="space-y-1.5">
              {analysis.weak_areas.map((w) => (
                <li key={w} className="flex items-start gap-2 text-sm text-gray-700">
                  <span className="text-orange-400 mt-0.5">⚠</span> {w}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {/* Role CTA */}
        {roles?.recommended_roles?.length > 0 && (
          <div className="pt-2 border-t border-gray-100">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                <span className="font-semibold text-gray-800">{roles.recommended_roles.length}</span> roles matched
                &nbsp;·&nbsp; top match:{" "}
                <span className="font-semibold text-indigo-600">
                  {roles.recommended_roles[0].role} ({roles.recommended_roles[0].match_score}%)
                </span>
              </p>
              <Link
                to={`/roles/${analysis.candidate_id}`}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-xl transition-colors"
              >
                View Role Recommendations →
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
