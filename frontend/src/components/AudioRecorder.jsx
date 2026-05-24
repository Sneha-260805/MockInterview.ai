/**
 * AudioRecorder — Phase 8: Audio Intelligence
 *
 * Optional audio recording panel that sits below the typed-answer textarea.
 * Records via the browser MediaRecorder API, uploads to /api/scoring/audio,
 * and returns the transcript + behavioral scores to the parent.
 *
 * Props:
 *   sessionId      {string}   — passed to backend for session association
 *   questionNumber {number}   — 1-based; passed to backend for question matching
 *   onTranscript   {fn(text)} — called with transcript text when analysis is done
 *   onResult       {fn(data)} — called with the full AudioAnalysisResponse
 *   disabled       {boolean}  — locks controls while the answer is submitted
 */

import { useEffect, useRef, useState } from "react";
import { analyzeAudio } from "../services/interviewService";

// ── State machine ─────────────────────────────────────────────────────────────
const RS = {
  idle:       "idle",
  requesting: "requesting",   // waiting for mic permission
  recording:  "recording",
  uploading:  "uploading",
  done:       "done",
  error:      "error",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtSeconds(s) {
  const m = Math.floor(s / 60).toString().padStart(2, "0");
  const sec = (s % 60).toString().padStart(2, "0");
  return `${m}:${sec}`;
}

function rateColor(rate) {
  return rate === "medium"
    ? "text-green-600"
    : rate === "fast"
    ? "text-orange-500"
    : "text-blue-500";
}
function rateLabel(rate) {
  return rate === "fast" ? "Fast" : rate === "slow" ? "Slow" : "Medium";
}
function hesitationColor(level) {
  return level === "low" ? "text-green-600" : level === "high" ? "text-red-500" : "text-yellow-500";
}
function pitchLabel(stability) {
  if (stability === "stable")   return "Stable";
  if (stability === "variable") return "Variable";
  if (stability === "monotone") return "Monotone";
  return null;
}
function pitchColor(stability) {
  return stability === "stable" ? "text-green-600" : stability === "variable" ? "text-orange-500" : "text-blue-500";
}

function ScorePill({ label, score, color }) {
  return (
    <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-3 py-2 min-w-[64px]">
      <span className={`text-lg font-extrabold tabular-nums leading-none ${color}`}>{score}</span>
      <span className="text-[10px] text-gray-400 mt-0.5 text-center leading-tight">{label}</span>
    </div>
  );
}

function scoreColor(s) {
  return s >= 70 ? "text-green-600" : s >= 50 ? "text-yellow-500" : "text-orange-500";
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AudioRecorder({
  sessionId,
  questionNumber,
  onTranscript,
  onResult,
  disabled = false,
}) {
  const [recState,    setRecState]    = useState(RS.idle);
  const [elapsed,     setElapsed]     = useState(0);
  const [error,       setError]       = useState("");
  const [result,      setResult]      = useState(null);
  const [expanded,    setExpanded]    = useState(false);

  const mediaRecRef  = useRef(null);
  const chunksRef    = useRef([]);
  const timerRef     = useRef(null);
  const streamRef    = useRef(null);

  // ── Cleanup on unmount ──────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // ── Start recording ─────────────────────────────────────────────────────────
  async function startRecording() {
    setError("");
    setResult(null);
    setRecState(RS.requesting);

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch {
      setError("Microphone access denied. Please allow mic access and try again.");
      setRecState(RS.error);
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    // Pick the best supported MIME type
    const mimeType = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg",
    ].find((t) => MediaRecorder.isTypeSupported(t)) ?? "";

    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    mediaRecRef.current = rec;

    rec.ondataavailable = (e) => {
      if (e.data?.size > 0) chunksRef.current.push(e.data);
    };

    rec.onstop = handleRecordingStop;
    rec.start(250); // collect chunks every 250 ms

    setElapsed(0);
    setRecState(RS.recording);
    timerRef.current = setInterval(() => setElapsed((t) => t + 1), 1000);
  }

  // ── Stop recording ──────────────────────────────────────────────────────────
  function stopRecording() {
    clearInterval(timerRef.current);
    mediaRecRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
  }

  // ── Upload + analyse ────────────────────────────────────────────────────────
  async function handleRecordingStop() {
    setRecState(RS.uploading);
    const blob = new Blob(chunksRef.current, { type: "audio/webm" });

    try {
      const data = await analyzeAudio({ audioBlob: blob, sessionId, questionNumber });
      setResult(data);
      setRecState(RS.done);
      onResult?.(data);
      if (data.transcript && !data.transcript.startsWith("[")) {
        onTranscript?.(data.transcript);
      }
    } catch (err) {
      setError(err.message || "Audio analysis failed. You can still type your answer.");
      setRecState(RS.error);
    }
  }

  // ── Re-record ───────────────────────────────────────────────────────────────
  function reset() {
    setRecState(RS.idle);
    setElapsed(0);
    setResult(null);
    setError("");
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  // Collapsed toggle bar (always visible in answer section)
  const isLocked = disabled && recState === RS.idle;

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      {/* ── Header / toggle ───────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => setExpanded((x) => !x)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          {recState === RS.recording ? (
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0" />
          ) : recState === RS.done ? (
            <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5 text-gray-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
          )}
          <span className="text-xs font-semibold text-gray-700">
            {recState === RS.recording
              ? `Recording… ${fmtSeconds(elapsed)}`
              : recState === RS.uploading
              ? "Analysing audio…"
              : recState === RS.done
              ? "Audio analysis complete"
              : "Record your answer (optional)"}
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* ── Body ──────────────────────────────────────────────────────────── */}
      {expanded && (
        <div className="p-4 space-y-4">

          {/* ── Controls ────────────────────────────────────────────────── */}
          {(recState === RS.idle || recState === RS.error) && (
            <div className="space-y-3">
              <p className="text-xs text-gray-500 leading-relaxed">
                Record your spoken answer. The AI will transcribe it and score your
                communication clarity, speaking pace, and confidence.
              </p>
              <button
                type="button"
                onClick={startRecording}
                disabled={isLocked}
                className="flex items-center gap-2 px-4 py-2.5 bg-red-500 hover:bg-red-600
                  text-white rounded-xl text-sm font-semibold transition-colors
                  disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="8" />
                </svg>
                Start Recording
              </button>
              {recState === RS.error && (
                <p className="text-xs text-red-600">{error}</p>
              )}
            </div>
          )}

          {recState === RS.requesting && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <svg className="w-4 h-4 animate-spin text-brand-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Waiting for microphone permission…
            </div>
          )}

          {recState === RS.recording && (
            <div className="space-y-3">
              {/* Animated waveform */}
              <div className="flex items-end justify-center gap-1 h-10">
                {[3, 6, 9, 7, 4, 8, 5, 10, 6, 3, 7, 5].map((h, i) => (
                  <div
                    key={i}
                    className="w-1.5 bg-red-400 rounded-full"
                    style={{
                      height: `${h * 4}px`,
                      animation: `pulse 0.${6 + (i % 4)}s ease-in-out infinite alternate`,
                      animationDelay: `${i * 0.07}s`,
                    }}
                  />
                ))}
              </div>
              <style>{`@keyframes pulse { from { transform: scaleY(0.5); } to { transform: scaleY(1); } }`}</style>
              <div className="flex items-center justify-between">
                <span className="text-sm font-mono font-semibold text-red-600">
                  {fmtSeconds(elapsed)}
                </span>
                <button
                  type="button"
                  onClick={stopRecording}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-900 hover:bg-gray-800
                    text-white rounded-xl text-sm font-semibold transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="4" y="4" width="16" height="16" rx="2" />
                  </svg>
                  Stop & Analyse
                </button>
              </div>
            </div>
          )}

          {recState === RS.uploading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <svg className="w-4 h-4 animate-spin text-brand-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Transcribing and scoring your audio…
            </div>
          )}

          {/* ── Results ─────────────────────────────────────────────────── */}
          {recState === RS.done && result && (
            <div className="space-y-4">

              {/* Invalid audio warning */}
              {result.status === "invalid_audio" && (
                <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5">
                  <svg className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                  </svg>
                  <p className="text-xs text-amber-700 leading-relaxed">
                    Unable to reliably analyse communication due to insufficient audio quality.
                    {result.reason ? ` ${result.reason}` : ""} Please re-record with clearer speech.
                  </p>
                </div>
              )}

              {/* Mode badge + metadata */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-[10px] font-semibold px-2 py-1 rounded-full border uppercase tracking-wide
                  ${result.mode === "fallback"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : result.status === "invalid_audio"
                    ? "bg-red-50 text-red-600 border-red-200"
                    : "bg-green-50 text-green-700 border-green-200"}`}
                >
                  {result.mode === "fallback"
                    ? "Audio analysis"
                    : result.status === "invalid_audio"
                    ? "Insufficient audio"
                    : "Whisper transcription"}
                </span>
                {result.duration_seconds && (
                  <span className="text-xs text-gray-400">
                    {result.duration_seconds}s · {result.word_count ?? "?"} words
                    {result.words_per_minute ? ` · ${Math.round(result.words_per_minute)} wpm` : ""}
                  </span>
                )}
              </div>

              {/* Score pills — only shown for valid audio */}
              {result.status !== "invalid_audio" && (
                <div className="flex items-center gap-2 flex-wrap">
                  <ScorePill
                    label="Confidence"
                    score={result.confidence_score}
                    color={scoreColor(result.confidence_score)}
                  />
                  <ScorePill
                    label="Clarity"
                    score={result.communication_clarity_score}
                    color={scoreColor(result.communication_clarity_score)}
                  />
                  {/* Pace */}
                  <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-3 py-2 min-w-[64px]">
                    <span className={`text-sm font-bold leading-none ${rateColor(result.speaking_rate)}`}>
                      {rateLabel(result.speaking_rate)}
                    </span>
                    <span className="text-[10px] text-gray-400 mt-0.5">Pace</span>
                  </div>
                  {/* Pauses */}
                  <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-3 py-2 min-w-[64px]">
                    <span className="text-lg font-extrabold tabular-nums leading-none text-gray-700">
                      {result.pause_count}
                    </span>
                    <span className="text-[10px] text-gray-400 mt-0.5">Pauses</span>
                  </div>
                  {/* Filler words */}
                  {result.filler_word_count != null && result.mode !== "fallback" && (
                    <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-3 py-2 min-w-[64px]">
                      <span className={`text-lg font-extrabold tabular-nums leading-none
                        ${result.filler_ratio > 0.10 ? "text-red-500" : result.filler_ratio > 0.05 ? "text-yellow-500" : "text-green-600"}`}>
                        {result.filler_word_count}
                      </span>
                      <span className="text-[10px] text-gray-400 mt-0.5">Fillers</span>
                    </div>
                  )}
                  {/* Hesitation level */}
                  {result.hesitation_level && result.mode !== "fallback" && (
                    <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-3 py-2 min-w-[64px]">
                      <span className={`text-sm font-bold leading-none capitalize ${hesitationColor(result.hesitation_level)}`}>
                        {result.hesitation_level.charAt(0).toUpperCase() + result.hesitation_level.slice(1)}
                      </span>
                      <span className="text-[10px] text-gray-400 mt-0.5">Hesitation</span>
                    </div>
                  )}
                  {/* Pitch stability */}
                  {result.pitch_stability && result.pitch_stability !== "unavailable" && (
                    <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-3 py-2 min-w-[64px]">
                      <span className={`text-sm font-bold leading-none ${pitchColor(result.pitch_stability)}`}>
                        {pitchLabel(result.pitch_stability)}
                      </span>
                      <span className="text-[10px] text-gray-400 mt-0.5">Pitch</span>
                    </div>
                  )}
                </div>
              )}

              {/* Analysis notes */}
              {result.analysis_notes && result.analysis_notes.length > 0 && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-3 space-y-1">
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                    Analysis Notes
                  </p>
                  {result.analysis_notes.map((note, i) => (
                    <div key={i} className="flex items-start gap-1.5">
                      <span className="text-gray-400 mt-0.5 shrink-0">·</span>
                      <span className="text-xs text-gray-600 leading-relaxed">{note}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Transcript */}
              {result.status !== "invalid_audio" && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                    Transcript
                  </p>
                  <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {result.transcript}
                  </p>
                  {result.transcript && !result.transcript.startsWith("[") && (
                    <button
                      type="button"
                      onClick={() => onTranscript?.(result.transcript)}
                      className="mt-2 text-xs text-brand-600 hover:text-brand-700 font-medium underline underline-offset-2"
                    >
                      Use transcript as typed answer
                    </button>
                  )}
                </div>
              )}

              {/* Re-record */}
              <button
                type="button"
                onClick={reset}
                className="text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2 transition-colors"
              >
                Re-record
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
