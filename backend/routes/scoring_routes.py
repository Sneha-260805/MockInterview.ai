"""
Phases 8 & 9 — Audio and Video scoring routes.

POST /api/scoring/audio
  Accepts a multipart form with:
    audio           — audio file (webm, wav, mp3, ogg, …)
    session_id      — (optional) interview session to attach scores to
    question_number — (optional) 1-based question index

POST /api/scoring/video
  Accepts a multipart form with:
    video           — video clip (webm/mp4) or image frame (jpeg/png)
    session_id      — (optional) interview session to attach scores to
    question_number — (optional) 1-based question index

POST /api/scoring/combined
  Accepts both audio and video in a single multipart request and analyses
  them in parallel (asyncio.gather) to avoid sequential blocking.
  Returns { audio: AudioAnalysisResponse, video: VideoAnalysisResponse }.

All endpoints persist results to the session so the final feedback report
can upgrade behavioral_mode beyond 'placeholder'.
"""

import asyncio
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from models.audio import AudioAnalysisResponse
from models.video import VideoAnalysisResponse
from services import audio_analyzer, video_analyzer
from database import store
from database.connection import get_db, is_using_memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scoring", tags=["scoring"])

_MAX_AUDIO_BYTES = 25 * 1024 * 1024   # 25 MB
_MAX_VIDEO_BYTES = 50 * 1024 * 1024   # 50 MB


@router.post("/audio", response_model=AudioAnalysisResponse)
async def analyze_audio(
    audio: UploadFile = File(..., description="Audio recording from the browser"),
    session_id:      Optional[str] = Form(None),
    question_number: Optional[int] = Form(None),
):
    """
    Transcribe and score an audio answer.

    - Uses faster-whisper if installed; otherwise returns heuristic scores.
    - Stores result on the session (audio_scores list) so the final report
      can upgrade behavioral_mode from 'placeholder' to 'audio'.
    """
    # ── Validate file ─────────────────────────────────────────────────────────
    file_bytes = await audio.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    if len(file_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds the {_MAX_AUDIO_BYTES // (1024*1024)} MB limit.",
        )

    # ── Analyse ───────────────────────────────────────────────────────────────
    result = await audio_analyzer.analyze(
        file_bytes,
        filename=audio.filename or "audio.webm",
    )

    # ── Persist to session (skip invalid audio — don't pollute scoring) ─────────
    if session_id and session_id.strip() and result.get("status") != "invalid_audio":
        audio_entry: dict = {
            "question_number":             question_number,
            "confidence_score":            result["confidence_score"],
            "communication_clarity_score": result["communication_clarity_score"],
            "pause_count":                 result["pause_count"],
            "speaking_rate":               result["speaking_rate"],
            "words_per_minute":            result.get("words_per_minute"),
            "filler_word_count":           result.get("filler_word_count"),
            "filler_ratio":                result.get("filler_ratio"),
            "hesitation_level":            result.get("hesitation_level"),
            "pitch_stability":             result.get("pitch_stability"),
            "analysis_notes":              result.get("analysis_notes", []),
            "transcript":                  result["transcript"],
            "mode":                        result["mode"],
            "metrics_source":              result.get("metrics_source"),
            "hesitation_count":            result.get("hesitation_count"),
            "hesitation_rate":             result.get("hesitation_rate"),
            "pause_rate_per_minute":       result.get("pause_rate_per_minute"),
            "tone_proxy":                  result.get("tone_proxy"),
            # Rich orchestrator fields (Member 2 multimodal intelligence)
            "recommendation_to_orchestrator": result.get("recommendation_to_orchestrator"),
            "coaching_tip":                result.get("coaching_tip"),
            "audio_reasoning_summary":     result.get("audio_reasoning_summary"),
            "pace_label":                  result.get("pace_label"),
            "detected_issue":              result.get("detected_issue"),
            "speaking_rate_wpm":           result.get("words_per_minute"),
        }

        # Always update in-memory store
        store.append_audio_score(session_id, audio_entry)

        # Also push to MongoDB when active (non-fatal if it fails)
        if not is_using_memory():
            try:
                db = get_db()
                await db["interview_sessions"].update_one(
                    {"session_id": session_id},
                    {"$push": {"audio_scores": audio_entry}},
                )
            except Exception:
                pass

    return AudioAnalysisResponse(**result)


# ── Video ─────────────────────────────────────────────────────────────────────

@router.post("/video", response_model=VideoAnalysisResponse)
async def analyze_video(
    video:           UploadFile      = File(..., description="Webcam clip or snapshot frame"),
    session_id:      Optional[str]  = Form(None),
    question_number: Optional[int]  = Form(None),
):
    """
    Phase 9 — Analyse a video clip or single image frame for visual cues.

    Supports:
      • Short webm/mp4 clips  → frames extracted with OpenCV
      • JPEG/PNG snapshots    → analysed as a single frame
      • Fallback mode         → heuristic scores (no OpenCV required)

    Persists engagement, framing, stability, and movement scores on the
    session so the final report can use camera-derived engagement instead
    of the word-count heuristic.
    """
    file_bytes = await video.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Video file is empty.")

    if len(file_bytes) > _MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Video file exceeds the {_MAX_VIDEO_BYTES // (1024*1024)} MB limit.",
        )

    result = await video_analyzer.analyze(
        file_bytes,
        filename=video.filename or "capture.webm",
    )

    if session_id and session_id.strip():
        video_entry: dict = {
            "question_number":   question_number,
            "status":            result.get("status", "ok"),
            "engagement_score":  result.get("engagement_score"),
            "framing_score":     result.get("framing_score"),
            "stability_score":   result.get("stability_score"),
            "movement_activity": result.get("movement_activity"),
            "mode":              result["mode"],
            # Rich orchestrator fields (Member 2 multimodal intelligence)
            "recommendation_to_orchestrator": result.get("recommendation_to_orchestrator"),
            "visual_reasoning_summary":       result.get("visual_reasoning_summary"),
            "nervousness_proxy_score":        result.get("nervousness_proxy_score"),
            "looking_away_proxy_score":       result.get("looking_away_proxy_score"),
            "posture_proxy_score":            result.get("posture_proxy_score"),
            "eye_contact_proxy_score":        result.get("eye_contact_proxy_score"),
            "stress_indicator":               result.get("stress_indicator"),
            "stress_nervousness_indicator":   result.get("stress_nervousness_indicator"),
            "analysis_notes":                 result.get("analysis_notes", []),
            "frames_analyzed":                result.get("frames_analyzed"),
            "face_detection_rate":            result.get("face_detection_rate"),
            "face_presence_score":            result.get("face_presence_score"),
            "face_centering_score":           result.get("face_centering_score"),
            "movement_stability_score":       result.get("movement_stability_score"),
        }
        store.append_video_score(session_id, video_entry)

        if not is_using_memory():
            try:
                db = get_db()
                await db["interview_sessions"].update_one(
                    {"session_id": session_id},
                    {"$push": {"video_scores": video_entry}},
                )
            except Exception:
                pass

    return VideoAnalysisResponse(**result)


# ── Combined (parallel audio + video) ────────────────────────────────────────

@router.post("/combined")
async def analyze_combined(
    audio:           UploadFile      = File(..., description="Audio recording"),
    video:           UploadFile      = File(..., description="Webcam clip or snapshot"),
    session_id:      Optional[str]  = Form(None),
    question_number: Optional[int]  = Form(None),
):
    """
    Analyse audio and video **in parallel** (asyncio.gather) in a single
    request.  This eliminates the sequential-blocking problem that caused
    timeouts when both pipelines were called independently.

    Returns:
      {
        "audio": AudioAnalysisResponse,
        "video": VideoAnalysisResponse
      }

    Both results are also persisted to the session (same as individual
    endpoints) so the final report can use all derived scores.
    """
    # ── Read uploads ──────────────────────────────────────────────────────────
    audio_bytes = await audio.read()
    video_bytes = await video.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")
    if not video_bytes:
        raise HTTPException(status_code=400, detail="Video file is empty.")
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail=f"Audio exceeds {_MAX_AUDIO_BYTES // (1024*1024)} MB limit.")
    if len(video_bytes) > _MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail=f"Video exceeds {_MAX_VIDEO_BYTES // (1024*1024)} MB limit.")

    # ── Run both analyses in parallel — neither blocks the other ──────────────
    logger.info(
        "combined: launching audio (%d B) + video (%d B) in parallel%s",
        len(audio_bytes), len(video_bytes),
        f" [session={session_id}]" if session_id else "",
    )
    audio_coro = audio_analyzer.analyze(audio_bytes, filename=audio.filename or "audio.webm")
    video_coro = video_analyzer.analyze(video_bytes, filename=video.filename or "capture.webm")

    audio_result, video_result = await asyncio.gather(
        audio_coro, video_coro, return_exceptions=True
    )

    # ── Graceful degradation — one failure must not kill both results ─────────
    if isinstance(audio_result, Exception):
        logger.warning("combined: audio analysis raised %s: %s", type(audio_result).__name__, audio_result)
        audio_result = {
            "status": "ok", "transcript": "[audio analysis failed]",
            "confidence_score": 50, "communication_clarity_score": 50,
            "pause_count": 0, "speaking_rate": "medium",
            "words_per_minute": 0.0, "filler_word_count": 0, "filler_ratio": 0.0,
            "hesitation_level": "low", "pitch_stability": "unavailable",
            "analysis_notes": ["Audio analysis encountered an error."],
            "mode": "fallback", "word_count": 0, "duration_seconds": 0.0,
            "reason": str(audio_result),
        }

    if isinstance(video_result, Exception):
        logger.warning("combined: video analysis raised %s: %s", type(video_result).__name__, video_result)
        video_result = {
            "status": "ok", "engagement_score": 50, "framing_score": 50,
            "stability_score": None, "movement_activity": "medium",
            "mode": "fallback", "frames_analyzed": 0, "face_detection_rate": 0.0,
            "analysis_notes": ["Video analysis encountered an error."],
            "warning": None,
        }

    # ── Persist to session ────────────────────────────────────────────────────
    if session_id and session_id.strip():
        if audio_result.get("status") != "invalid_audio":
            audio_entry = {
                "question_number":             question_number,
                "confidence_score":            audio_result["confidence_score"],
                "communication_clarity_score": audio_result["communication_clarity_score"],
                "pause_count":                 audio_result["pause_count"],
                "speaking_rate":               audio_result["speaking_rate"],
                "words_per_minute":            audio_result.get("words_per_minute"),
                "filler_word_count":           audio_result.get("filler_word_count"),
                "filler_ratio":                audio_result.get("filler_ratio"),
                "hesitation_level":            audio_result.get("hesitation_level"),
                "pitch_stability":             audio_result.get("pitch_stability"),
                "analysis_notes":              audio_result.get("analysis_notes", []),
                "transcript":                  audio_result["transcript"],
                "mode":                        audio_result["mode"],
                # Rich orchestrator fields (Member 2 multimodal intelligence)
                "metrics_source":              audio_result.get("metrics_source"),
                "hesitation_count":            audio_result.get("hesitation_count"),
                "hesitation_rate":             audio_result.get("hesitation_rate"),
                "pause_rate_per_minute":       audio_result.get("pause_rate_per_minute"),
                "tone_proxy":                  audio_result.get("tone_proxy"),
                "recommendation_to_orchestrator": audio_result.get("recommendation_to_orchestrator"),
                "coaching_tip":                audio_result.get("coaching_tip"),
                "audio_reasoning_summary":     audio_result.get("audio_reasoning_summary"),
                "pace_label":                  audio_result.get("pace_label"),
                "detected_issue":              audio_result.get("detected_issue"),
                "speaking_rate_wpm":           audio_result.get("words_per_minute"),
            }
            store.append_audio_score(session_id, audio_entry)

        video_entry = {
            "question_number":   question_number,
            "status":            video_result.get("status", "ok"),
            "engagement_score":  video_result.get("engagement_score"),
            "framing_score":     video_result.get("framing_score"),
            "stability_score":   video_result.get("stability_score"),
            "movement_activity": video_result.get("movement_activity"),
            "mode":              video_result["mode"],
            # Rich orchestrator fields (Member 2 multimodal intelligence)
            "recommendation_to_orchestrator": video_result.get("recommendation_to_orchestrator"),
            "visual_reasoning_summary":       video_result.get("visual_reasoning_summary"),
            "nervousness_proxy_score":        video_result.get("nervousness_proxy_score"),
            "looking_away_proxy_score":       video_result.get("looking_away_proxy_score"),
            "posture_proxy_score":            video_result.get("posture_proxy_score"),
            "eye_contact_proxy_score":        video_result.get("eye_contact_proxy_score"),
            "stress_indicator":               video_result.get("stress_indicator"),
            "stress_nervousness_indicator":   video_result.get("stress_nervousness_indicator"),
            "analysis_notes":                 video_result.get("analysis_notes", []),
            "frames_analyzed":                video_result.get("frames_analyzed"),
            "face_detection_rate":            video_result.get("face_detection_rate"),
            "face_presence_score":            video_result.get("face_presence_score"),
            "face_centering_score":           video_result.get("face_centering_score"),
            "movement_stability_score":       video_result.get("movement_stability_score"),
        }
        store.append_video_score(session_id, video_entry)

        if not is_using_memory():
            try:
                db = get_db()
                mongo_ops = [
                    db["interview_sessions"].update_one(
                        {"session_id": session_id},
                        {"$push": {"video_scores": video_entry}},
                    ),
                ]
                # Only push audio_entry to Mongo if it was defined (valid audio)
                if audio_result.get("status") != "invalid_audio":
                    mongo_ops.append(
                        db["interview_sessions"].update_one(
                            {"session_id": session_id},
                            {"$push": {"audio_scores": audio_entry}},
                        )
                    )
                await asyncio.gather(*mongo_ops)
            except Exception:
                pass

    return {
        "audio": AudioAnalysisResponse(**audio_result),
        "video": VideoAnalysisResponse(**video_result),
    }
