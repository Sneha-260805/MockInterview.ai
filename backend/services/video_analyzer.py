"""
Phase 9 — Video Intelligence analyser (improved heuristics).

Accepts either a short video clip (webm/mp4) or a single JPEG/PNG frame
and returns:
    engagement_score   — 0-100  face presence rate (honest proxy)
    framing_score      — 0-100  face centred in frame (centering proxy, not gaze)
    stability_score    — 0-100  face-size variance across frames (distance stability)
                                None when fewer than 3 valid frames exist
    movement_activity  — "low" | "medium" | "high"  head-movement intensity
    status             — "ok" | "invalid_analysis"
    analysis_notes     — list of human-readable explanations for each metric
    mode               — "opencv_mediapipe" | "opencv" | "fallback"

Engine priority
───────────────
1. OpenCV + MediaPipe  (pip install opencv-python mediapipe)
     → MediaPipe FaceDetection on every sampled frame
2. OpenCV only         (pip install opencv-python)
     → Haar Cascade face detector bundled with cv2
3. Fallback            → conservative seeded heuristics (no frames opened)

Invalid analysis gate
─────────────────────
face_detection_rate < 0.30 OR fewer than 3 face detections → status="invalid_analysis"
All scores set to None.  Frontend should display an explicit warning.

Score calibration targets
─────────────────────────
Poor session:    15–40
Average session: 50–70
Strong session:  75–90

Frame sampling fix
──────────────────
Uses seek-based uniform sampling when frame count is known.
Falls back to sequential step-sampling (every 15th frame) for WebM
containers where CAP_PROP_FRAME_COUNT returns 0.
"""

import logging
import math
import os
import random
import tempfile
from pathlib import Path
from statistics import mean, stdev
from typing import Optional

logger = logging.getLogger(__name__)

# ── Engine detection ──────────────────────────────────────────────────────────

_CV2_AVAILABLE = False
_MP_AVAILABLE  = False
_FACE_CASCADE  = None          # lazy-loaded OpenCV Haar Cascade

try:
    import cv2                 # type: ignore
    import numpy as np         # type: ignore
    _CV2_AVAILABLE = True
    logger.info("Video analyser: OpenCV available.")
except ImportError:
    logger.info(
        "Video analyser: OpenCV not found — using fallback. "
        "Install with: pip install opencv-python"
    )

if _CV2_AVAILABLE:
    try:
        import mediapipe as mp  # type: ignore
        _MP_AVAILABLE = True
        logger.info("Video analyser: MediaPipe available (best accuracy).")
    except ImportError:
        logger.info(
            "Video analyser: MediaPipe not found — using OpenCV Haar Cascade. "
            "Install with: pip install mediapipe"
        )


def _get_face_cascade():
    global _FACE_CASCADE
    if _FACE_CASCADE is None and _CV2_AVAILABLE:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _FACE_CASCADE = cv2.CascadeClassifier(path)
    return _FACE_CASCADE


# ── Validity thresholds ───────────────────────────────────────────────────────

_MIN_DETECTION_RATE = 0.30   # below this → invalid_analysis
_MIN_VALID_FACES    = 3      # fewer face detections → stability_score = None

# ── Frame result dict:
#   has_face, cx, cy, size, center_dist  (all positions in [0, 1] relative coords)

_MISS = {"has_face": False, "cx": 0.5, "cy": 0.5, "size": 0.0, "center_dist": 0.5}


# ── Per-frame face detectors ──────────────────────────────────────────────────

def _face_info_haar(frame_bgr) -> dict:
    cascade = _get_face_cascade()
    gray    = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces   = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
    if not len(faces):
        return _MISS.copy()
    h, w        = frame_bgr.shape[:2]
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])   # largest face
    cx   = (x + fw / 2) / w
    cy   = (y + fh / 2) / h
    size = (fw * fh) / (w * h)
    return {"has_face": True, "cx": cx, "cy": cy, "size": size,
            "center_dist": math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2)}


def _face_info_mediapipe(frame_bgr, detector) -> dict:
    rgb    = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = detector.process(rgb)
    if not result.detections:
        return _MISS.copy()
    det  = result.detections[0]          # highest-confidence detection
    bb   = det.location_data.relative_bounding_box
    cx   = bb.xmin + bb.width  / 2
    cy   = bb.ymin + bb.height / 2
    size = bb.width * bb.height
    return {"has_face": True, "cx": cx, "cy": cy, "size": size,
            "center_dist": math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2)}


# ── Score computation ─────────────────────────────────────────────────────────

def _scores_from_frames(frame_data: list[dict]) -> dict:
    """
    Compute all video scores from per-frame face detection results.

    Returns status="invalid_analysis" (all scores None) when:
      - no frames at all
      - face_detection_rate < _MIN_DETECTION_RATE
      - fewer than _MIN_VALID_FACES frames had a face

    Otherwise returns status="ok" with calibrated scores and explanation notes.
    """
    total     = len(frame_data)
    if total == 0:
        return {
            "status":              "invalid_analysis",
            "reason":              "No frames could be extracted from the video.",
            "engagement_score":    None,
            "framing_score":       None,
            "stability_score":     None,
            "movement_activity":   None,
            "face_detection_rate": 0.0,
            "analysis_notes":      [],
            "warning":             None,
        }

    with_face      = [f for f in frame_data if f["has_face"]]
    detection_rate = len(with_face) / total

    # ── Invalid analysis gate ─────────────────────────────────────────────────
    if detection_rate < _MIN_DETECTION_RATE or len(with_face) < _MIN_VALID_FACES:
        if len(with_face) < _MIN_VALID_FACES:
            reason = (
                f"Only {len(with_face)} frame(s) with a detected face — "
                "too few for reliable analysis. Ensure good lighting and "
                "that your face is clearly visible."
            )
        else:
            reason = (
                f"Face detected in only {round(detection_rate * 100)}% of frames "
                "(threshold: 30%). Check lighting, camera angle, and frame position."
            )
        return {
            "status":              "invalid_analysis",
            "reason":              reason,
            "engagement_score":    None,
            "framing_score":       None,
            "stability_score":     None,
            "movement_activity":   None,
            "face_detection_rate": round(detection_rate, 3),
            "analysis_notes":      [],
            "warning":             None,
        }

    notes: list[str] = []

    # ── Engagement: face presence rate ────────────────────────────────────────
    # 30% → ~37 (poor)  |  70% → ~66 (average)  |  100% → ~88 (strong)
    engagement = int(max(15, min(88, 15 + detection_rate * 73)))

    if detection_rate >= 0.85:
        notes.append("Face remained consistently visible throughout.")
    elif detection_rate >= 0.60:
        notes.append("Face was visible in most frames.")
    else:
        notes.append("Frequent face loss detected — check lighting and camera angle.")

    # ── Framing: face centred in frame (outlier-filtered) ─────────────────────
    # Trim worst 10% of center_dist values to avoid single bad frames tanking score.
    # center_dist=0.0 → 88 (strong)  |  0.20 → 55 (average)  |  0.40 → 22 (poor)
    dists      = sorted(f["center_dist"] for f in with_face)
    trim_count = max(1, int(len(dists) * 0.90))   # keep best 90%
    avg_dist   = mean(dists[:trim_count])
    framing    = int(max(15, min(88, 88 - avg_dist * 165)))

    if avg_dist < 0.08:
        notes.append("Face remained consistently centered in frame.")
    elif avg_dist < 0.18:
        notes.append("Face was generally well-positioned in frame.")
    else:
        notes.append("Face was frequently off-center — try adjusting your camera position.")

    # ── Stability: face-size variance across frames ───────────────────────────
    # Measures how much the face size (relative bounding box area) varies —
    # a proxy for camera-distance consistency.
    # Null when fewer than _MIN_VALID_FACES detections exist.
    # std=0.00 → 85 (strong)  |  std=0.05 → 63 (average)  |  std=0.10 → 41 (poor)
    warning: Optional[str] = None
    stability: Optional[int]

    if len(with_face) >= _MIN_VALID_FACES:
        sizes    = [f["size"] for f in with_face]
        size_std = stdev(sizes)
        stability = int(max(15, min(85, 85 - size_std * 440)))

        if size_std < 0.025:
            notes.append("Camera distance remained stable throughout.")
        elif size_std < 0.065:
            notes.append("Minor variation in camera distance observed.")
        else:
            notes.append("Significant movement or distance changes detected.")
    else:
        stability = None
        warning   = "Not enough valid frames for stability analysis."

    # ── Movement activity: frame-to-frame head displacement (outlier-filtered) ─
    # Discard top 10% movement spikes before averaging to ignore single-frame
    # head turns (e.g. adjusting glasses) that aren't indicative of overall behaviour.
    if len(with_face) >= 4:
        raw_moves = [
            math.sqrt((with_face[i]["cx"] - with_face[i - 1]["cx"]) ** 2
                    + (with_face[i]["cy"] - with_face[i - 1]["cy"]) ** 2)
            for i in range(1, len(with_face))
        ]
        sorted_moves = sorted(raw_moves)
        trim_m       = max(1, int(len(sorted_moves) * 0.90))
        avg_move     = mean(sorted_moves[:trim_m])

        if avg_move > 0.050:
            movement = "high"
            notes.append("High movement intensity observed — try to maintain a stable position.")
        elif avg_move > 0.020:
            movement = "medium"
            notes.append("Moderate head movement detected.")
        else:
            movement = "low"
            notes.append("Movement was minimal — good physical composure.")
    elif detection_rate < 0.50:
        movement = "high"
        notes.append("Too few stable frames to measure movement accurately.")
    elif detection_rate < 0.75:
        movement = "medium"
    else:
        movement = "low"

    return {
        "status":              "ok",
        "engagement_score":    engagement,
        "framing_score":       framing,
        "stability_score":     stability,
        "movement_activity":   movement,
        "face_detection_rate": round(detection_rate, 3),
        "analysis_notes":      notes,
        "warning":             warning,
    }


# ── Frame extraction ──────────────────────────────────────────────────────────

def _extract_frames(video_path: str, max_frames: int = 30) -> list:
    """
    Extract up to max_frames uniformly distributed frames.

    When CAP_PROP_FRAME_COUNT is reliable (mp4, known containers):
      → seek to uniformly-spaced positions for true uniform sampling.

    When it returns 0 (common with WebM):
      → read sequentially, keeping every 15th frame.
      At 30 fps, step=15 samples every 0.5 s → ~30 samples in a 15 s clip,
      spread across the entire recording rather than only the first second.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []

    if total > 0:
        # Seek-based uniform sampling — covers the full duration
        positions = [int(i * total / max_frames) for i in range(max_frames)]
        for pos in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
    else:
        # Sequential step-sampling for WebM / unknown frame count
        step = 15
        idx  = 0
        while len(frames) < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step == 0:
                frames.append(frame)
            idx += 1

    cap.release()
    return frames


def _bytes_to_frame(image_bytes: bytes):
    """Decode raw image bytes (JPEG/PNG) to an OpenCV BGR array."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)


# ── Engine runners ────────────────────────────────────────────────────────────

def _analyze_opencv_mediapipe(frames: list) -> dict:
    mp_face    = mp.solutions.face_detection   # type: ignore[reportPossiblyUnbound]
    frame_data = []
    with mp_face.FaceDetection(min_detection_confidence=0.5) as detector:
        for frame in frames:
            frame_data.append(_face_info_mediapipe(frame, detector))
    scores = _scores_from_frames(frame_data)
    scores.update(mode="opencv_mediapipe", frames_analyzed=len(frames))
    return scores


def _analyze_opencv(frames: list) -> dict:
    frame_data = [_face_info_haar(f) for f in frames]
    scores     = _scores_from_frames(frame_data)
    scores.update(mode="opencv", frames_analyzed=len(frames))
    return scores


# ── Fallback analyser ─────────────────────────────────────────────────────────

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _analyze_fallback(file_bytes: bytes, is_image: bool) -> dict:
    """
    Conservative heuristic scores when computer-vision libraries are unavailable.

    Scores are seeded from file_size for reproducibility but kept in the
    average range (35-70) — not the optimistic 80+ of the old implementation.
    stability_score is always None because it requires real frame data.
    """
    file_size = len(file_bytes)
    rng       = random.Random(file_size % 99_991)

    if is_image:
        frame_est = 1
    else:
        duration_s = max(1.0, file_size / 600_000.0)
        frame_est  = max(3, int(duration_s * 30 / 15))

    # Average-range scores (35–70), not the old generous 65–88
    engagement  = int(max(35, min(70, 52 + rng.randint(-12, 12))))
    framing     = int(max(30, min(68, 50 + rng.randint(-12, 12))))
    face_rate   = round(min(1.0, max(0.35, 0.62 + rng.uniform(-0.18, 0.18))), 2)

    movement_r = rng.random()
    movement   = "low" if movement_r > 0.65 else ("high" if movement_r < 0.20 else "medium")

    return {
        "status":              "ok",
        "engagement_score":    engagement,
        "framing_score":       framing,
        "stability_score":     None,    # cannot compute without real frame data
        "movement_activity":   movement,
        "mode":                "fallback",
        "frames_analyzed":     frame_est,
        "face_detection_rate": face_rate,
        "analysis_notes":      [
            "Scores are estimated — install opencv-python for real face-detection analysis.",
        ],
        "warning": "Stability analysis requires opencv-python.",
    }


# ── Public entry point ────────────────────────────────────────────────────────

async def analyze(file_bytes: bytes, filename: str = "capture.webm") -> dict:
    """
    Accepts raw bytes (video or image) and returns a VideoAnalysisResponse dict.
    Writes to a temp file only when cv2 is available to extract frames.
    Always cleans up the temp file.
    Falls back gracefully if any engine step fails.
    """
    ext      = Path(filename).suffix.lower()
    is_image = ext in _IMAGE_EXTENSIONS

    if not _CV2_AVAILABLE:
        return _analyze_fallback(file_bytes, is_image)

    suffix = ext or (".jpg" if is_image else ".webm")
    tmp    = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(file_bytes)
        tmp.flush()
        tmp.close()

        if is_image:
            frame  = _bytes_to_frame(file_bytes)
            frames = [frame] if frame is not None else []
        else:
            frames = _extract_frames(tmp.name, max_frames=30)

        if not frames:
            logger.warning("Video analyser: no frames extracted — using fallback.")
            return _analyze_fallback(file_bytes, is_image)

        if _MP_AVAILABLE:
            return _analyze_opencv_mediapipe(frames)
        else:
            return _analyze_opencv(frames)

    except Exception as exc:
        logger.warning(
            "Video analysis failed (%s) — using fallback: %s",
            "mediapipe" if _MP_AVAILABLE else "opencv",
            exc,
        )
        return _analyze_fallback(file_bytes, is_image)

    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
