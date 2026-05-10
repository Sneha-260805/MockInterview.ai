/**
 * InterviewMonitor — Unified Audio + Video Recording Panel
 *
 * Replaces the separate AudioRecorder and VideoRecorder components with a
 * single, cohesive interview monitoring experience.
 *
 * One "Enable Camera & Microphone" button → one shared MediaStream.
 * One "Start Recording" button          → both mic and camera record.
 * One "Stop & Analyze" button           → both stop, single combined upload
 *                                         via POST /api/scoring/combined
 *                                         (asyncio.gather on the backend).
 *
 * State machine
 * ─────────────
 *   idle        → idle panel, "Enable Camera & Microphone" CTA
 *   requesting  → waiting for browser permission dialog
 *   ready       → preview live, "Start Recording" button shown
 *   recording   → REC overlay, animated audio waveform, timer, "Stop & Analyze"
 *   processing  → dimmed overlay, "Transcribing & analyzing…" spinner
 *   done        → results: communication scores + presence scores + transcript
 *   error       → error message + retry
 *
 * Props
 * ─────
 *   sessionId      {string}   — session ID forwarded to backend
 *   questionNumber {number}   — 1-based question index
 *   onTranscript   {fn(text)} — called with Whisper transcript (to prefill answer textarea)
 *   onAudioResult  {fn(data)} — called with AudioAnalysisResponse
 *   onVideoResult  {fn(data)} — called with VideoAnalysisResponse
 *   disabled       {boolean}  — disables recording controls while answer is submitted
 */

import { useEffect, useRef, useState } from "react";
import { analyzeMediaCombined } from "../services/interviewService";

// ── State machine ─────────────────────────────────────────────────────────────

const MS = {
  idle:       "idle",
  requesting: "requesting",
  ready:      "ready",
  recording:  "recording",
  processing: "processing",
  done:       "done",
  error:      "error",
};

const MAX_RECORD_SECONDS = 120; // 2-minute hard cap

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTime(s) {
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}

function scoreColor(s) {
  if (s == null) return "text-gray-300";
  return s >= 70 ? "text-green-600" : s >= 50 ? "text-yellow-500" : "text-orange-500";
}

function rateColor(r) {
  return r === "medium" ? "text-green-600" : r === "fast" ? "text-orange-500" : "text-blue-500";
}

function motionColor(m) {
  return m === "low" ? "text-green-600" : m === "medium" ? "text-yellow-500" : "text-red-500";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ScorePill({ label, value, colorFn }) {
  const color = value == null ? "text-gray-300" : colorFn(value);
  return (
    <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-2.5 py-2 min-w-[54px]">
      <span className={`text-sm font-extrabold leading-none ${color}`}>
        {value ?? "—"}
      </span>
      <span className="text-[9px] text-gray-400 mt-0.5 text-center leading-tight">{label}</span>
    </div>
  );
}

function TextPill({ label, value, colorFn }) {
  const color = value ? colorFn(value) : "text-gray-300";
  return (
    <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-2.5 py-2 min-w-[54px]">
      <span className={`text-sm font-extrabold leading-none capitalize ${color}`}>
        {value ?? "—"}
      </span>
      <span className="text-[9px] text-gray-400 mt-0.5 text-center leading-tight">{label}</span>
    </div>
  );
}

function AudioWaveform() {
  const heights = [3, 7, 5, 9, 6, 4, 8, 5, 10, 4, 7, 3, 6, 8, 4];
  return (
    <div className="flex items-end justify-center gap-0.5 h-6">
      <style>{`@keyframes imwave{from{transform:scaleY(.3)}to{transform:scaleY(1)}}`}</style>
      {heights.map((h, i) => (
        <div
          key={i}
          className="w-1 bg-red-400 rounded-full origin-bottom"
          style={{
            height: `${h * 2}px`,
            animation: `imwave 0.${4 + (i % 6)}s ease-in-out infinite alternate`,
            animationDelay: `${i * 0.05}s`,
          }}
        />
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function InterviewMonitor({
  sessionId,
  questionNumber,
  onTranscript,
  onAudioResult,
  onVideoResult,
  disabled = false,
}) {
  const [ms,          setMs]          = useState(MS.idle);
  const [elapsed,     setElapsed]     = useState(0);
  const [error,       setError]       = useState("");
  const [audioResult, setAudioResult] = useState(null);
  const [videoResult, setVideoResult] = useState(null);

  const streamRef    = useRef(null);   // MediaStream (audio + video)
  const videoElemRef = useRef(null);   // <video> preview element
  const audioRecRef  = useRef(null);   // MediaRecorder for audio-only track
  const videoRecRef  = useRef(null);   // MediaRecorder for video track
  const audioChunks  = useRef([]);
  const videoChunks  = useRef([]);
  const timerRef     = useRef(null);
  const autoStopRef  = useRef(null);

  // ── Reset when question changes (keep preview active) ────────────────────────
  useEffect(() => {
    if (ms === MS.done || ms === MS.processing) {
      setAudioResult(null);
      setVideoResult(null);
      setError("");
      // Go back to ready if camera is still on, otherwise idle
      setMs(streamRef.current?.active ? MS.ready : MS.idle);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionNumber]);

  // ── Wire stream to preview <video> once it mounts ─────────────────────────
  useEffect(() => {
    if (videoElemRef.current && streamRef.current) {
      videoElemRef.current.srcObject = streamRef.current;
    }
  }, [ms]);

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clearInterval(timerRef.current);
      clearTimeout(autoStopRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // ── Enable camera + microphone ───────────────────────────────────────────
  async function enable() {
    setError("");
    setMs(MS.requesting);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
      });
      streamRef.current = stream;
      setMs(MS.ready);
    } catch {
      setError(
        "Camera and microphone access required. Please allow permissions in your browser and try again."
      );
      setMs(MS.error);
    }
  }

  // ── Start recording ───────────────────────────────────────────────────────
  function startRecording() {
    const stream = streamRef.current;
    if (!stream) return;

    audioChunks.current = [];
    videoChunks.current = [];

    // Audio-only recorder (clean audio for Whisper)
    const audioStream = new MediaStream(stream.getAudioTracks());
    const audioMime = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
    ].find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
    const aRec = new MediaRecorder(
      audioStream,
      audioMime ? { mimeType: audioMime } : undefined
    );
    aRec.ondataavailable = (e) => {
      if (e.data?.size > 0) audioChunks.current.push(e.data);
    };
    aRec.start(250); // collect every 250 ms
    audioRecRef.current = aRec;

    // Video recorder (full stream — backend uses video frames for OpenCV/MediaPipe)
    const videoMime = [
      "video/webm;codecs=vp9,opus",
      "video/webm;codecs=vp8,opus",
      "video/webm",
    ].find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
    const vRec = new MediaRecorder(
      stream,
      videoMime ? { mimeType: videoMime } : undefined
    );
    vRec.ondataavailable = (e) => {
      if (e.data?.size > 0) videoChunks.current.push(e.data);
    };
    vRec.start(500);
    videoRecRef.current = vRec;

    setElapsed(0);
    setMs(MS.recording);
    timerRef.current    = setInterval(() => setElapsed((t) => t + 1), 1000);
    autoStopRef.current = setTimeout(stopAndUpload, MAX_RECORD_SECONDS * 1000);
  }

  // ── Stop both recorders and upload ────────────────────────────────────────
  function stopAndUpload() {
    clearInterval(timerRef.current);
    clearTimeout(autoStopRef.current);
    setMs(MS.processing);

    let audioDone = false;
    let videoDone = false;
    let audioBlob = null;
    let videoBlob = null;

    function tryUpload() {
      if (!audioDone || !videoDone) return;
      doUpload(audioBlob, videoBlob);
    }

    const aRec = audioRecRef.current;
    const vRec = videoRecRef.current;

    if (aRec && aRec.state !== "inactive") {
      aRec.onstop = () => {
        audioBlob = new Blob(audioChunks.current, { type: "audio/webm" });
        audioDone = true;
        tryUpload();
      };
      aRec.stop();
    } else {
      audioBlob = new Blob(audioChunks.current, { type: "audio/webm" });
      audioDone = true;
    }

    if (vRec && vRec.state !== "inactive") {
      vRec.onstop = () => {
        videoBlob = new Blob(videoChunks.current, { type: "video/webm" });
        videoDone = true;
        tryUpload();
      };
      vRec.stop();
    } else {
      videoBlob = new Blob(videoChunks.current, { type: "video/webm" });
      videoDone = true;
    }

    // Handles the case where both were already stopped/null
    tryUpload();
  }

  // ── Send to /api/scoring/combined ─────────────────────────────────────────
  async function doUpload(audioBlob, videoBlob) {
    try {
      const { audio, video } = await analyzeMediaCombined({
        audioBlob,
        videoBlob,
        videoFilename: "recording.webm",
        sessionId,
        questionNumber,
      });

      setAudioResult(audio);
      setVideoResult(video);
      setMs(MS.done);
      onAudioResult?.(audio);
      onVideoResult?.(video);

      if (audio?.transcript && !audio.transcript.startsWith("[")) {
        onTranscript?.(audio.transcript);
      }
    } catch (err) {
      setError(err.message || "Analysis failed. Please try recording again.");
      setMs(MS.error);
    }
  }

  // ── Disable and tear down streams ─────────────────────────────────────────
  function disable() {
    clearInterval(timerRef.current);
    clearTimeout(autoStopRef.current);
    if (audioRecRef.current?.state !== "inactive") audioRecRef.current?.stop();
    if (videoRecRef.current?.state !== "inactive") videoRecRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setAudioResult(null);
    setVideoResult(null);
    setError("");
    setElapsed(0);
    setMs(MS.idle);
  }

  // ── Derived state flags ───────────────────────────────────────────────────
  const isActive     = [MS.ready, MS.recording, MS.processing, MS.done].includes(ms);
  const isRecording  = ms === MS.recording;
  const isProcessing = ms === MS.processing;
  const isDone       = ms === MS.done;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center gap-2">
          {/* Status icon */}
          {isRecording && (
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0" />
          )}
          {isDone && (
            <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          )}
          {isProcessing && (
            <svg className="w-3.5 h-3.5 animate-spin text-indigo-500 shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          {!isRecording && !isDone && !isProcessing && (
            <svg className="w-3.5 h-3.5 text-gray-500 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
            </svg>
          )}

          {/* Status text */}
          <span className="text-xs font-semibold text-gray-700">
            {ms === MS.idle       && "Interview Monitor"}
            {ms === MS.requesting && "Requesting access…"}
            {ms === MS.ready      && "Ready to record"}
            {ms === MS.recording  && `Recording  ${fmtTime(elapsed)}`}
            {ms === MS.processing && "Analyzing interview…"}
            {ms === MS.done       && "Analysis complete"}
            {ms === MS.error      && "Monitor error"}
          </span>
        </div>

        {/* Disable button */}
        {isActive && !isProcessing && (
          <button
            type="button"
            onClick={disable}
            className="text-[10px] text-gray-400 hover:text-red-500 transition-colors"
          >
            Disable
          </button>
        )}
      </div>

      <div className="p-3 space-y-3">

        {/* ── IDLE — Enable CTA ────────────────────────────────────────────── */}
        {ms === MS.idle && (
          <div className="space-y-3">
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Enable your camera and microphone for real-time engagement, framing, and
              communication analysis throughout your interview.
            </p>
            <button
              type="button"
              onClick={enable}
              disabled={disabled}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-indigo-600
                hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold transition-colors
                disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72
                     M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9
                     A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
              </svg>
              Enable Camera &amp; Microphone
            </button>
          </div>
        )}

        {/* ── REQUESTING ───────────────────────────────────────────────────── */}
        {ms === MS.requesting && (
          <div className="flex items-center gap-2.5 text-xs text-gray-500 py-2">
            <svg className="w-4 h-4 animate-spin text-indigo-500 shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Waiting for camera &amp; microphone permission…
          </div>
        )}

        {/* ── Webcam preview (ready / recording / processing / done) ────────── */}
        {[MS.ready, MS.recording, MS.processing, MS.done].includes(ms) && (
          <div className="relative rounded-xl overflow-hidden bg-black aspect-video">
            <video
              ref={videoElemRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover scale-x-[-1]"
            />

            {/* REC overlay — shown while recording */}
            {isRecording && (
              <div className="absolute inset-0 pointer-events-none">
                {/* Top-left: REC badge + timer */}
                <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/60 rounded-full px-2.5 py-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                  <span className="text-[10px] text-white font-mono font-semibold">
                    {fmtTime(elapsed)}
                  </span>
                </div>
                {/* Top-right: mic indicator */}
                <div className="absolute top-2 right-2 flex items-center gap-1 bg-black/60 rounded-full px-2 py-1">
                  <svg className="w-2.5 h-2.5 text-green-400" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 14a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3zm5-3a5 5 0 01-10 0H5a7 7 0 0014 0h-2z" />
                  </svg>
                  <span className="text-[9px] text-green-300 font-medium">mic</span>
                </div>
                {/* Bottom: animated audio waveform */}
                <div className="absolute bottom-2 inset-x-0 flex flex-col items-center gap-1">
                  <AudioWaveform />
                </div>
              </div>
            )}

            {/* Processing overlay */}
            {isProcessing && (
              <div className="absolute inset-0 bg-black/55 flex flex-col items-center justify-center gap-2.5">
                <svg className="w-6 h-6 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span className="text-[10px] text-white/90 text-center leading-snug px-6">
                  Transcribing audio &amp; analyzing video…
                </span>
              </div>
            )}

            {/* Done badge overlay */}
            {isDone && (
              <div className="absolute top-2 right-2">
                <div className="flex items-center gap-1 bg-green-500/90 rounded-full px-2 py-0.5">
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  <span className="text-[9px] text-white font-semibold">Done</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── START RECORDING button (ready state) ─────────────────────────── */}
        {ms === MS.ready && (
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-red-500
              hover:bg-red-600 text-white rounded-xl text-xs font-semibold transition-colors
              disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="8" />
            </svg>
            Start Recording
          </button>
        )}

        {/* ── STOP & ANALYZE button (recording state) ──────────────────────── */}
        {ms === MS.recording && (
          <button
            type="button"
            onClick={stopAndUpload}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-gray-900
              hover:bg-gray-800 text-white rounded-xl text-xs font-semibold transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
              <rect x="4" y="4" width="16" height="16" rx="2" />
            </svg>
            Stop &amp; Analyze
          </button>
        )}

        {/* ── ERROR state ───────────────────────────────────────────────────── */}
        {ms === MS.error && (
          <div className="space-y-2.5">
            <p className="text-xs text-red-600 leading-relaxed">{error}</p>
            <button
              type="button"
              onClick={() => { setError(""); setMs(MS.idle); }}
              className="text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2 transition-colors"
            >
              Try again
            </button>
          </div>
        )}

        {/* ── RESULTS (done state) ─────────────────────────────────────────── */}
        {isDone && audioResult && videoResult && (
          <div className="space-y-3">

            {/* Analysis mode badges */}
            <div className="flex flex-wrap gap-1.5">
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border uppercase tracking-wide
                ${audioResult.mode === "fallback"
                  ? "bg-amber-50 text-amber-700 border-amber-200"
                  : "bg-green-50 text-green-700 border-green-200"}`}
              >
                {audioResult.mode === "fallback" ? "Audio: Heuristic" : "Audio: Whisper AI"}
              </span>
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border uppercase tracking-wide
                ${videoResult.mode === "fallback"
                  ? "bg-amber-50 text-amber-700 border-amber-200"
                  : "bg-green-50 text-green-700 border-green-200"}`}
              >
                {videoResult.mode === "fallback"          ? "Video: Heuristic"
                  : videoResult.mode === "opencv_mediapipe" ? "Video: MediaPipe AI"
                  : "Video: OpenCV"}
              </span>
            </div>

            {/* ── Communication metrics (audio) ────────────────────────────── */}
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 flex items-center gap-1.5">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75
                       m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                </svg>
                Communication
              </p>
              <div className="flex flex-wrap gap-1.5">
                <ScorePill
                  label="Confidence"
                  value={audioResult.confidence_score}
                  colorFn={scoreColor}
                />
                <ScorePill
                  label="Clarity"
                  value={audioResult.communication_clarity_score}
                  colorFn={scoreColor}
                />
                <TextPill
                  label="Pace"
                  value={
                    audioResult.speaking_rate === "medium" ? "Med"
                      : audioResult.speaking_rate === "fast" ? "Fast"
                      : "Slow"
                  }
                  colorFn={rateColor}
                />
                <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-2.5 py-2 min-w-[54px]">
                  <span className="text-sm font-extrabold leading-none text-gray-700">
                    {audioResult.pause_count ?? "—"}
                  </span>
                  <span className="text-[9px] text-gray-400 mt-0.5">Pauses</span>
                </div>
                {audioResult.words_per_minute > 0 && (
                  <div className="flex flex-col items-center bg-white border border-gray-200 rounded-xl px-2.5 py-2 min-w-[54px]">
                    <span className="text-sm font-extrabold leading-none text-gray-700">
                      {Math.round(audioResult.words_per_minute)}
                    </span>
                    <span className="text-[9px] text-gray-400 mt-0.5">WPM</span>
                  </div>
                )}
              </div>
            </div>

            {/* ── Presence metrics (video) ──────────────────────────────────── */}
            {videoResult.status !== "invalid_analysis" && (
              <div>
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 flex items-center gap-1.5">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round"
                      d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5
                         c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639
                         C20.577 16.49 16.64 19.5 12 19.5c-4.641 0-8.573-3.007-9.964-7.178z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Presence
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {videoResult.engagement_score != null && (
                    <ScorePill label="Engagement" value={videoResult.engagement_score} colorFn={scoreColor} />
                  )}
                  {videoResult.framing_score != null && (
                    <ScorePill label="Framing" value={videoResult.framing_score} colorFn={scoreColor} />
                  )}
                  {videoResult.stability_score != null && (
                    <ScorePill label="Stability" value={videoResult.stability_score} colorFn={scoreColor} />
                  )}
                  {videoResult.movement_activity && (
                    <TextPill
                      label="Motion"
                      value={
                        videoResult.movement_activity === "low"  ? "Calm"
                          : videoResult.movement_activity === "medium" ? "Mod"
                          : "High"
                      }
                      colorFn={motionColor}
                    />
                  )}
                </div>
                {videoResult.warning && (
                  <p className="text-[10px] text-amber-600 mt-1.5">{videoResult.warning}</p>
                )}
              </div>
            )}

            {/* Invalid video gate */}
            {videoResult.status === "invalid_analysis" && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                <p className="text-[10px] text-amber-700 leading-relaxed">
                  {videoResult.reason ?? "Low face visibility — try better lighting or centre yourself in frame."}
                </p>
              </div>
            )}

            {/* ── Transcript ─────────────────────────────────────────────────── */}
            {audioResult.transcript && !audioResult.transcript.startsWith("[") && (
              <div className="bg-gray-50 border border-gray-200 rounded-xl p-2.5">
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">
                  Transcript
                </p>
                <p className="text-[11px] text-gray-700 leading-relaxed line-clamp-5">
                  {audioResult.transcript}
                </p>
                <button
                  type="button"
                  onClick={() => onTranscript?.(audioResult.transcript)}
                  className="mt-1.5 text-[10px] text-indigo-600 hover:text-indigo-700 font-medium
                    underline underline-offset-2 transition-colors"
                >
                  Use as answer ↗
                </button>
              </div>
            )}

            {/* Heuristic mode notice */}
            {(audioResult.mode === "fallback" || videoResult.mode === "fallback") && (
              <p className="text-[10px] text-amber-600 leading-snug">
                Heuristic scores shown — install{" "}
                {audioResult.mode === "fallback" ? "faster-whisper" : ""}
                {audioResult.mode === "fallback" && videoResult.mode === "fallback" ? " + " : ""}
                {videoResult.mode === "fallback" ? "opencv-python" : ""}{" "}
                for AI-powered analysis.
              </p>
            )}

            {/* Record again */}
            <button
              type="button"
              onClick={() => {
                setAudioResult(null);
                setVideoResult(null);
                setMs(streamRef.current?.active ? MS.ready : MS.idle);
              }}
              className="text-[10px] text-gray-400 hover:text-gray-700 underline underline-offset-2 transition-colors"
            >
              Record again
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
