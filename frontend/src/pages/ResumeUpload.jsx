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
      setAnalyzeError(S.error);
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
    blue:   "bg-blue-50 text-blue-700 border-blue-100",
    green:  "bg-green-50 text-green-700 border-green-100",
    purple: "bg-purple-50 text-purple-700 border-purple-100",
    gray:   "bg-gray-100 text-gray-600 border-gray-200",
    orange: "bg-orange-50 text-orange-700 border-orange-100",
    red:    "bg-red-50 text-red-700 border-red-100",
    teal:   "bg-teal-50 text-teal-700 border-teal-100",
  };
  return (
    <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${styles[variant] ?? styles.blue}`}>
      {label}
    </span>
  );
}

function Section({ title, badge, children, accent = "gray" }) {
  const border = {
    gray:   "border-gray-100",
    indigo: "border-indigo-100",
    orange: "border-orange-100",
    red:    "border-red-100",
    green:  "border-green-100",
    violet: "border-violet-100",
  }[accent] ?? "border-gray-100";

  return (
    <div className={`border-t ${border} pt-4`}>
      <div className="flex items-center gap-2 mb-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{title}</p>
        {badge && (
          <span className="text-[10px] font-semibold text-gray-400 bg-gray-100 border border-gray-200 rounded-full px-2 py-0.5">
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function LevelBadge({ level }) {
  const map = {
    junior: { label: "Junior", cls: "bg-blue-100 text-blue-700" },
    mid:    { label: "Mid-level", cls: "bg-yellow-100 text-yellow-700" },
    senior: { label: "Senior", cls: "bg-green-100 text-green-700" },
  };
  const { label, cls } = map[level] || { label: level, cls: "bg-gray-100 text-gray-600" };
  return (
    <span className={`text-xs font-semibold px-3 py-1 rounded-full ${cls}`}>{label}</span>
  );
}

function AnalysisPanel({ analysis, roles }) {
  const [showClaims, setShowClaims] = useState(false);

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

      <div className="p-6 space-y-5">

        {/* Domains */}
        {analysis.domains?.length > 0 && (
          <Section title="Domain Exposure">
            <div className="flex flex-wrap gap-2">
              {analysis.domains.map((d) => <Tag key={d} label={d} variant="purple" />)}
            </div>
          </Section>
        )}

        {/* Strong Skills (new) */}
        {analysis.strong_skills?.length > 0 && (
          <Section title="Strongest Skills" accent="green">
            <div className="flex flex-wrap gap-2">
              {analysis.strong_skills.map((s) => (
                <span key={s} className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-green-50 border border-green-200 text-green-800">
                  <svg className="w-3 h-3 text-green-600" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  {s}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* All Skills */}
        {analysis.skills?.length > 0 && (
          <Section title={`All Detected Skills`} badge={`${analysis.skills.length} found`}>
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
          <Section title="Projects" badge={`${analysis.projects.length} found`}>
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

        {/* Project Deep Dives (new) */}
        {analysis.project_deep_dives?.length > 0 && (
          <Section title="Interview Deep-Dive Candidates" accent="violet">
            <div className="space-y-3">
              {analysis.project_deep_dives.map((dive) => (
                <div key={dive.project} className="bg-violet-50 border border-violet-100 rounded-xl px-4 py-3">
                  <div className="flex items-start gap-2">
                    <svg className="w-4 h-4 text-violet-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <div className="flex-1">
                      <p className="font-semibold text-sm text-violet-900">{dive.project}</p>
                      <p className="text-xs text-violet-600 mt-0.5">{dive.why_selected}</p>
                      {dive.probe_topics?.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {dive.probe_topics.map((t) => (
                            <span key={t} className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white border border-violet-200 text-violet-700">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Claims to Verify (new) */}
        {analysis.claims_to_verify?.length > 0 && (
          <Section title="Claims to Verify in Interview" accent="orange">
            <button
              onClick={() => setShowClaims((v) => !v)}
              className="w-full flex items-center justify-between text-xs text-orange-700 font-semibold bg-orange-50 border border-orange-200 rounded-xl px-4 py-2.5 mb-3 hover:bg-orange-100 transition-colors"
            >
              <span className="flex items-center gap-2">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {analysis.claims_to_verify.length} resume claims the interview will probe
              </span>
              <svg className={`w-4 h-4 transition-transform ${showClaims ? "rotate-180" : ""}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>

            {showClaims && (
              <div className="space-y-3">
                {analysis.claims_to_verify.map((c, i) => (
                  <div key={i} className="border border-orange-100 rounded-xl p-4 bg-white">
                    <p className="text-sm font-semibold text-gray-800 mb-1">
                      Claim: <span className="text-orange-700">{c.claim}</span>
                    </p>
                    <p className="text-xs text-gray-500 mb-2">
                      <span className="font-medium text-gray-600">Why verify: </span>
                      {c.why_verify}
                    </p>
                    <div className="flex items-start gap-2 bg-orange-50 rounded-lg px-3 py-2">
                      <svg className="w-3.5 h-3.5 text-orange-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                      </svg>
                      <p className="text-xs text-orange-800 italic">{c.probe_question}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
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

        {/* Interview Risks (new) */}
        {analysis.interview_risks?.length > 0 && (
          <Section title="Interview Risk Signals" accent="red">
            <ul className="space-y-1.5">
              {analysis.interview_risks.map((r) => (
                <li key={r} className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  <svg className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                  </svg>
                  {r}
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

        {/* Role signals (new) */}
        {analysis.role_signals?.length > 0 && (
          <Section title="Role Signals Detected" accent="indigo">
            <ul className="space-y-1.5">
              {analysis.role_signals.map((sig) => (
                <li key={sig} className="flex items-start gap-2 text-xs text-indigo-700">
                  <span className="text-indigo-400 mt-0.5 shrink-0">→</span> {sig}
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
