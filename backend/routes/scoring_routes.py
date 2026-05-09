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

Both endpoints persist results to the session so the final feedback report
can upgrade behavioral_mode beyond 'placeholder'.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from models.audio import AudioAnalysisResponse
from models.video import VideoAnalysisResponse
from services import audio_analyzer, video_analyzer
from database import store
from database.connection import get_db, is_using_memory

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
