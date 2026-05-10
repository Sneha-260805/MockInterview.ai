/**
 * VideoRecorder — Phase 9: Video Intelligence
 *
 * Compact sidebar webcam panel that lets the user:
 *   1. Enable camera → see a live preview
 *   2. Capture Frame → instant JPEG snapshot → backend analysis
 *   3. Record 15s    → short webm clip      → backend analysis
 *
 * Scores returned: engagement_score, framing_score, stability_score, movement_activity
 *
 * Props
 *   sessionId      {string}   — attached to backend request for session storage
 *   questionNumber {number}   — 1-based question index
 *   onResult       {fn(data)} — called with the VideoAnalysisResponse
 *   disabled       {boolean}  — locks controls while answer is being evaluated
 */

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { analyzeVideo } from "../services/interviewService";

// ── State machine ─────────────────────────────────────────────────────────────
const VS = {
  idle:       "idle",
  requesting: "requesting",
  preview:    "preview",     // webcam live, awaiting user action
  capturing:  "capturing",   // frame snapshot in flight
  recording:  "recording",   // MediaRecorder active
  uploading:  "uploading",
  done:       "done",
  error:      "error",
};

const MAX_RECORD_SECONDS = 120;

// ── Helpers ───────────────────────────────────────────────────────────────────
function scoreColor(s) {
  return s >= 70 ? "text-green-600" : s >= 50 ? "text-yellow-500" : "text-orange-500";
}
function stressColor(s) {
  return s === "low" ? "text-green-600" : s === "medium" ? "text-yellow-500" : "text-red-500";
}
function stressLabel(s) {
  return s === "low" ? "Calm" : s === "medium" ? "Moderate" : "Elevated";
}

function MiniScore({ label, value, colorFn, isText = false }) {
  const isNull = value == null;
  return (
    <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-2.5 py-2 min-w-[58px]">
      <span className={`text-sm font-extrabold leading-none ${isNull ? "text-gray-300" : colorFn(value)}`}>
        {isNull ? "—" : isText ? stressLabel(value) : value}
      </span>
      <span className="text-[9px] text-gray-400 mt-0.5 text-center leading-tight">{label}</span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const VideoRecorder = forwardRef(function VideoRecorder({
  sessionId,
  questionNumber,
  onResult,
  disabled = false,
  autoStart = false,
}, ref) {
  const [vs,       setVs]       = useState(VS.idle);
  const [elapsed,  setElapsed]  = useState(0);
  const [error,    setError]    = useState("");
  const [result,   setResult]   = useState(null);

  const previewRef  = useRef(null);   // <video> element
  const streamRef   = useRef(null);   // MediaStream
  const recRef      = useRef(null);   // MediaRecorder
  const chunksRef   = useRef([]);
  const timerRef    = useRef(null);
  const autoStopRef = useRef(null);
  const uploadPromiseRef = useRef(null);
  const pendingStopResolveRef = useRef(null);
  const enabledOnceRef = useRef(false);

  // ── Wire stream to <video> element when stream changes ────────────────────
  useEffect(() => {
    if (previewRef.current && streamRef.current) {
      previewRef.current.srcObject = streamRef.current;
    }
  }, [vs]);   // re-run after setVs(VS.preview) renders the <video>

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clearInterval(timerRef.current);
      clearTimeout(autoStopRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // ── Enable camera ─────────────────────────────────────────────────────────
  async function enableCamera() {
    setError("");
    setVs(VS.requesting);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;
      setVs(VS.preview);
      return stream;
    } catch {
      setError("Camera access denied. Please allow camera access and try again.");
      setVs(VS.error);
      return null;
    }
  }

  useEffect(() => {
    if (!autoStart || disabled || enabledOnceRef.current) return;
    enabledOnceRef.current = true;
    enableCamera().then((stream) => {
      if (stream) startRecording(stream);
    });
  }, [autoStart, disabled]);

  useEffect(() => {
    setResult(null);
    setElapsed(0);
    setError("");
    if (autoStart && streamRef.current && !disabled) {
      startRecording(streamRef.current);
    }
  }, [questionNumber]);

  // ── Capture single frame ──────────────────────────────────────────────────
  async function captureFrame() {
    const video = previewRef.current;
    if (!video) return;
    setVs(VS.capturing);

    const canvas = document.createElement("canvas");
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext("2d").drawImage(video, 0, 0);

    canvas.toBlob(async (blob) => {
      if (!blob) { setError("Could not capture frame."); setVs(VS.preview); return; }
      await upload(blob, "frame.jpg");
    }, "image/jpeg", 0.85);
  }

  // ── Start video recording ─────────────────────────────────────────────────
  function startRecording(streamOverride = null) {
    chunksRef.current = [];
    const stream = streamOverride || streamRef.current;
    if (!stream) {
      setError("Camera is not active. Enable camera first.");
      setVs(VS.error);
      return;
    }
    const mimeType = [
      "video/webm;codecs=vp9,opus",
      "video/webm;codecs=vp8,opus",
      "video/webm",
    ].find((t) => MediaRecorder.isTypeSupported(t)) ?? "";

    const rec = new MediaRecorder(
      stream,
      mimeType ? { mimeType } : undefined,
    );
    recRef.current = rec;

    rec.ondataavailable = (e) => { if (e.data?.size > 0) chunksRef.current.push(e.data); };
    rec.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: "video/webm" });
      uploadPromiseRef.current = upload(blob, "recording.webm");
      const data = await uploadPromiseRef.current;
      pendingStopResolveRef.current?.(data);
      pendingStopResolveRef.current = null;
    };

    rec.start(500);
    setElapsed(0);
    setVs(VS.recording);
    timerRef.current    = setInterval(() => setElapsed((t) => t + 1), 1000);
    autoStopRef.current = setTimeout(stopRecording, MAX_RECORD_SECONDS * 1000);
  }

  function stopRecording() {
    clearInterval(timerRef.current);
    clearTimeout(autoStopRef.current);
    if (recRef.current?.state === "recording") {
      recRef.current.stop();
    }
    setVs(VS.uploading);
  }

  // ── Upload and analyse ────────────────────────────────────────────────────
  async function upload(blob, filename) {
    setVs(VS.uploading);
    try {
      const data = await analyzeVideo({ videoBlob: blob, filename, sessionId, questionNumber });
      setResult(data);
      setVs(VS.done);
      onResult?.(data);
      return data;
    } catch (err) {
      setError(err.message || "Video analysis failed.");
      setVs(VS.preview);   // stay in preview so user can retry
      return null;
    }
  }

  async function finishTurn() {
    if (vs === VS.recording && recRef.current?.state === "recording") {
      return new Promise((resolve) => {
        pendingStopResolveRef.current = resolve;
        stopRecording();
      });
    }
    if (vs === VS.uploading && uploadPromiseRef.current) {
      return uploadPromiseRef.current;
    }
    if ((vs === VS.preview || vs === VS.done) && !result && previewRef.current) {
      return new Promise((resolve) => {
        const video = previewRef.current;
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        canvas.getContext("2d").drawImage(video, 0, 0);
        canvas.toBlob(async (blob) => {
          if (!blob) return resolve(null);
          resolve(await upload(blob, "frame.jpg"));
        }, "image/jpeg", 0.85);
      });
    }
    return result;
  }

  useImperativeHandle(ref, () => ({
    finishTurn,
    startMonitoring: async () => {
      const stream = streamRef.current || await enableCamera();
      if (stream && recRef.current?.state !== "recording") {
        startRecording(stream);
      }
    },
  }));

  // ── Disable camera ────────────────────────────────────────────────────────
  function disableCamera() {
    clearInterval(timerRef.current);
    clearTimeout(autoStopRef.current);
    recRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setResult(null);
    setVs(VS.idle);
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center gap-2">
          {vs === VS.recording && (
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0" />
          )}
          {vs === VS.done && (
            <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          )}
          {![VS.recording, VS.done].includes(vs) && (
            <svg className="w-3.5 h-3.5 text-gray-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
            </svg>
          )}
          <span className="text-xs font-semibold text-gray-700">
            {vs === VS.idle        && "Video Monitor (optional)"}
            {vs === VS.requesting  && "Requesting camera…"}
            {vs === VS.preview     && "Camera active"}
            {vs === VS.capturing   && "Capturing frame…"}
            {vs === VS.recording   && `Recording ${elapsed}s / ${MAX_RECORD_SECONDS}s`}
            {vs === VS.uploading   && "Analysing…"}
            {vs === VS.done        && "Analysis complete"}
            {vs === VS.error       && "Camera error"}
          </span>
        </div>
        {(vs === VS.preview || vs === VS.done) && (
          <button
            type="button"
            onClick={disableCamera}
            className="text-[10px] text-gray-400 hover:text-red-500 transition-colors"
          >
            Disable
          </button>
        )}
      </div>

      <div className="p-3 space-y-3">

        {/* ── Idle ───────────────────────────────────────────────────────── */}
        {vs === VS.idle && (
          <div className="space-y-2">
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Keep your camera on while answering. Engagement, framing, and
              stability help adapt the next question.
            </p>
            <button
              type="button"
              onClick={enableCamera}
              disabled={disabled}
              className="flex items-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-700
                text-white rounded-xl text-xs font-semibold transition-colors
                disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
              </svg>
              Start Camera Monitor
            </button>
          </div>
        )}

        {/* ── Requesting ─────────────────────────────────────────────────── */}
        {vs === VS.requesting && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <svg className="w-4 h-4 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Waiting for camera permission…
          </div>
        )}

        {/* ── Live preview (shown in preview, recording, done) ────────────── */}
        {[VS.preview, VS.recording, VS.capturing, VS.done].includes(vs) && (
          <div className="relative rounded-xl overflow-hidden bg-black aspect-video">
            <video
              ref={previewRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover scale-x-[-1]"   /* mirror effect */
            />
            {vs === VS.recording && (
              <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-black/60 rounded-full px-2 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                <span className="text-[10px] text-white font-mono">
                  {elapsed}s
                </span>
              </div>
            )}
            {vs === VS.done && result && (
              <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </div>
            )}
          </div>
        )}

        {/* ── Action buttons (preview state) ──────────────────────────────── */}
        {vs === VS.preview && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={captureFrame}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-indigo-600
                hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
              </svg>
              Capture
            </button>
            <button
              type="button"
              onClick={startRecording}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-red-500
                hover:bg-red-600 text-white rounded-xl text-xs font-semibold transition-colors"
            >
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="8" />
              </svg>
              Record Turn
            </button>
          </div>
        )}

        {/* ── Stop button (recording state) ────────────────────────────────── */}
        {vs === VS.recording && (
          <button
            type="button"
            onClick={stopRecording}
            className="w-full flex items-center justify-center gap-2 py-2 bg-gray-900
              hover:bg-gray-800 text-white rounded-xl text-xs font-semibold transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
              <rect x="4" y="4" width="16" height="16" rx="2" />
            </svg>
            Stop & Analyse
          </button>
        )}

        {/* ── Uploading ────────────────────────────────────────────────────── */}
        {vs === VS.uploading && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <svg className="w-4 h-4 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Analysing video…
          </div>
        )}

        {/* ── Results ──────────────────────────────────────────────────────── */}
        {vs === VS.done && result && (
          <div className="space-y-3">
            {result.status === "invalid_analysis" ? (
              /* Invalid analysis gate */
              <div className="bg-red-50 border border-red-200 rounded-xl px-3 py-2.5 space-y-1">
                <p className="text-xs font-semibold text-red-700">Analysis unsuccessful</p>
                <p className="text-[10px] text-red-600 leading-relaxed">
                  {result.reason ?? "Insufficient face visibility for reliable analysis."}
                </p>
              </div>
            ) : (
              <>
                {/* Mode badge */}
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-semibold px-2 py-1 rounded-full border uppercase tracking-wide
                    ${result.mode === "fallback"
                      ? "bg-amber-50 text-amber-700 border-amber-200"
                      : "bg-green-50 text-green-700 border-green-200"}`}
                  >
                    {result.mode === "fallback" ? "Heuristic"
                      : result.mode === "opencv_mediapipe" ? "MediaPipe"
                      : "OpenCV"}
                  </span>
                  {result.frames_analyzed != null && (
                    <span className="text-[10px] text-gray-400">
                      {result.frames_analyzed} frames · {Math.round((result.face_detection_rate ?? 0) * 100)}% face
                    </span>
                  )}
                </div>

                {/* Score pills */}
                <div className="flex flex-wrap gap-1.5">
                  <MiniScore label="Engagement" value={result.engagement_score}  colorFn={scoreColor} />
                  <MiniScore label="Framing"    value={result.framing_score}     colorFn={scoreColor} />
                  <MiniScore label="Stability"  value={result.stability_score}   colorFn={scoreColor} />
                  <MiniScore label="Motion"     value={result.movement_activity} colorFn={stressColor} isText />
                </div>

                {/* Warning */}
                {result.warning && (
                  <p className="text-[10px] text-amber-600">{result.warning}</p>
                )}

                {/* Analysis notes */}
                {result.analysis_notes?.length > 0 && (
                  <ul className="space-y-0.5">
                    {result.analysis_notes.map((note, i) => (
                      <li key={i} className="text-[10px] text-gray-500">· {note}</li>
                    ))}
                  </ul>
                )}
              </>
            )}

            {/* Re-analyse */}
            <button
              type="button"
              onClick={() => setVs(VS.preview)}
              className="text-[10px] text-gray-400 hover:text-gray-700 underline underline-offset-2 transition-colors"
            >
              Re-analyse
            </button>
          </div>
        )}

        {/* ── Error ────────────────────────────────────────────────────────── */}
        {vs === VS.error && (
          <div className="space-y-2">
            <p className="text-xs text-red-600">{error}</p>
            <button
              type="button"
              onClick={() => { setVs(VS.idle); setError(""); }}
              className="text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2"
            >
              Try again
            </button>
          </div>
        )}

        {/* Inline error when in preview state */}
        {vs === VS.preview && error && (
          <p className="text-[10px] text-red-500">{error}</p>
        )}
      </div>
    </div>
  );
});

export default VideoRecorder;
