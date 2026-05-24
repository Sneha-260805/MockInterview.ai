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
    blue:   "bg-blue-50 text-blue-700 border-blue-100",
    green:  "bg-green-50 text-green-700 border-green-100",
    purple: "bg-purple-50 text-purple-700 border-purple-100",
    gray:   "bg-gray-100 text-gray-600 border-gray-200",
    amber:  "bg-amber-50 text-amber-700 border-amber-200",
    red:    "bg-red-50 text-red-700 border-red-100",
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
  const hasAiStrongSkills = analysis.strong_skills?.length > 0;
  const hasAiWeakAreas = analysis.weak_or_missing_areas?.length > 0;

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

        {/* Work Experience */}
        {analysis.work_experience?.length > 0 && (
          <Section title={`Work Experience (${analysis.work_experience.length} found)`}>
            <div className="space-y-3">
              {analysis.work_experience.map((w, i) => (
                <div key={i} className="bg-gray-50 rounded-xl px-4 py-3">
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <p className="font-semibold text-sm text-gray-800">{w.company}</p>
                    {w.duration && (
                      <span className="text-xs text-gray-400 shrink-0">{w.duration}</span>
                    )}
                  </div>
                  {w.role && (
                    <p className="text-xs text-indigo-600 font-medium mt-0.5">{w.role}</p>
                  )}
                  {w.responsibilities?.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {w.responsibilities.slice(0, 3).map((r, j) => (
                        <li key={j} className="text-xs text-gray-500 flex items-start gap-1.5">
                          <span className="text-gray-300 mt-0.5 shrink-0">·</span>
                          <span className="line-clamp-1">{r}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Projects */}
        {analysis.projects?.length > 0 && (
          <Section title={`Projects (${analysis.projects.length} found)`}>
            <div className="space-y-3">
              {analysis.projects.map((p) => (
                <div key={p.name} className="bg-gray-50 rounded-xl px-4 py-3">
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <p className="font-semibold text-sm text-gray-800">{p.name}</p>
                    {p.duration && (
                      <span className="text-xs text-gray-400 shrink-0">{p.duration}</span>
                    )}
                  </div>
                  {/* Show structured description bullets if available, else summary */}
                  {p.description?.length > 0 ? (
                    <ul className="mt-1.5 space-y-0.5">
                      {p.description.slice(0, 3).map((line, i) => (
                        <li key={i} className="text-xs text-gray-500 flex items-start gap-1.5">
                          <span className="text-gray-300 mt-0.5 shrink-0">·</span>
                          <span className="line-clamp-2">{line}</span>
                        </li>
                      ))}
                    </ul>
                  ) : p.summary && p.summary !== "No description available." ? (
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">{p.summary}</p>
                  ) : null}
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

        {/* Certifications */}
        {analysis.certifications?.length > 0 && (
          <Section title={`Certifications (${analysis.certifications.length} found)`}>
            <div className="space-y-2">
              {analysis.certifications.map((c, i) => (
                <div key={i} className="flex items-start justify-between gap-2 bg-green-50 border border-green-100 rounded-xl px-4 py-2.5">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{c.name}</p>
                    {c.issuer && (
                      <p className="text-xs text-gray-500 mt-0.5">{c.issuer}</p>
                    )}
                  </div>
                  {c.date && (
                    <span className="text-xs text-gray-400 shrink-0 mt-0.5">{c.date}</span>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Achievements */}
        {analysis.achievements?.length > 0 && (
          <Section title="Achievements & Awards">
            <ul className="space-y-1.5">
              {analysis.achievements.map((a, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                  <span className="text-yellow-500 mt-0.5 shrink-0">★</span>
                  <span>{a}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {/* Strengths */}
        {!hasAiStrongSkills && analysis.strengths?.length > 0 && (
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
        {!hasAiWeakAreas && analysis.weak_areas?.length > 0 && (
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

        {/* ── Interview Intelligence (Gemini-powered) ──────────────────── */}
        {(() => {
          const hasIntelligence =
            analysis.strong_skills?.length > 0 ||
            analysis.weak_or_missing_areas?.length > 0 ||
            analysis.interview_risks?.length > 0 ||
            analysis.claims_to_verify?.length > 0 ||
            analysis.project_deep_dives?.length > 0 ||
            analysis.suggested_interview_probes?.length > 0;
          if (!hasIntelligence) return null;
          return (
            <div className="border-t-2 border-indigo-100 pt-5 space-y-5">
              {/* Section header */}
              <div className="flex items-center gap-2.5">
                <svg className="w-4 h-4 text-indigo-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                <span className="text-sm font-bold text-indigo-700">Interview Intelligence</span>
                <span className="flex-1 h-px bg-indigo-100" />
                <span className="text-[10px] font-semibold text-indigo-500 bg-indigo-50 px-2.5 py-1 rounded-full border border-indigo-100">
                  AI-powered
                </span>
              </div>

              {/* Strong Skills */}
              {analysis.strong_skills?.length > 0 && (
                <Section title="Strong Skills — Evidenced by Resume">
                  <div className="flex flex-wrap gap-2">
                    {analysis.strong_skills.map((s) => (
                      <span key={s} className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border bg-green-50 text-green-700 border-green-200">
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                        {s}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              {/* Weak / Missing Areas */}
              {analysis.weak_or_missing_areas?.length > 0 && (
                <Section title="Weak / Missing Areas">
                  <div className="flex flex-wrap gap-2">
                    {analysis.weak_or_missing_areas.map((s) => (
                      <Tag key={s} label={s} variant="amber" />
                    ))}
                  </div>
                </Section>
              )}

              {/* Interview Risks */}
              {analysis.interview_risks?.length > 0 && (
                <Section title="Interview Risks">
                  <div className="space-y-2">
                    {analysis.interview_risks.map((r, i) => (
                      <div key={i} className="flex items-start gap-2.5 bg-red-50 border border-red-100 rounded-xl px-3.5 py-2.5">
                        <svg className="w-4 h-4 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                        </svg>
                        <p className="text-sm text-red-800">{r}</p>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Claims to Verify — visually prominent */}
              {analysis.claims_to_verify?.length > 0 && (
                <Section title="Claims to Verify in Interview">
                  <div className="space-y-3">
                    {analysis.claims_to_verify.map((c, i) => (
                      <div key={i} className="bg-violet-50 border-2 border-violet-200 rounded-xl overflow-hidden">
                        <div className="px-4 py-2.5 bg-violet-100 border-b border-violet-200 flex items-start gap-2">
                          <svg className="w-3.5 h-3.5 text-violet-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803 7.5 7.5 0 0016.803 15.803z" />
                          </svg>
                          <div>
                            <p className="text-[10px] font-bold text-violet-600 uppercase tracking-wider mb-0.5">Claim</p>
                            <p className="text-sm font-semibold text-violet-900">"{c.claim}"</p>
                          </div>
                        </div>
                        <div className="px-4 py-3 space-y-2.5">
                          <div>
                            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Why verify</p>
                            <p className="text-xs text-gray-600 leading-relaxed">{c.why_verify}</p>
                          </div>
                          <div className="bg-white border border-violet-100 rounded-lg px-3 py-2.5">
                            <p className="text-[10px] font-bold text-violet-600 uppercase tracking-wider mb-1">Probe question</p>
                            <p className="text-xs text-violet-800 font-medium leading-relaxed">"{c.probe_question}"</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Project Deep Dives */}
              {analysis.project_deep_dives?.length > 0 && (
                <Section title="Project Deep Dives">
                  <div className="space-y-3">
                    {analysis.project_deep_dives.map((pd, i) => (
                      <div key={i} className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3">
                        <p className="text-sm font-semibold text-blue-900">{pd.project}</p>
                        <p className="text-xs text-blue-600 mt-0.5 leading-relaxed">{pd.why_selected}</p>
                        {pd.probe_topics?.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2.5">
                            {pd.probe_topics.map((t) => (
                              <span key={t} className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200">
                                {t}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Suggested Interview Probes */}
              {analysis.suggested_interview_probes?.length > 0 && (
                <Section title="Suggested Interview Probes">
                  <ul className="space-y-2">
                    {analysis.suggested_interview_probes.map((p, i) => (
                      <li key={i} className="flex items-start gap-2.5 bg-indigo-50 border border-indigo-100 rounded-xl px-3.5 py-2.5">
                        <span className="text-indigo-500 font-bold text-sm mt-0.5 shrink-0">?</span>
                        <p className="text-sm text-indigo-800">{p}</p>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}
            </div>
          );
        })()}

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
