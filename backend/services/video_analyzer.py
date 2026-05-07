"""
Phase 9 — Video Intelligence analyser.

Accepts either a short video clip (webm/mp4) or a single JPEG/PNG frame
and returns:
    engagement_score   — 0-100  face present and looking at camera
    eye_contact_score  — 0-100  face centred in frame (gaze proxy)
    posture_score      — 0-100  stable, consistent head size / position
    stress_indicator   — "low" | "medium" | "high"  (head-movement proxy)
    mode               — "opencv_mediapipe" | "opencv" | "fallback"

Engine priority
───────────────
1. OpenCV + MediaPipe  (pip install opencv-python mediapipe)
     → MediaPipe face detection on every sampled frame
2. OpenCV only         (pip install opencv-python)
     → Haar Cascade face detector; bundled with cv2 — no extra download
3. Fallback            → file-size heuristics, reproducible seeded scores

Image vs video detection
────────────────────────
Determined by file extension / MIME type of the uploaded filename.
Images (.jpg/.jpeg/.png/.webp) are analysed as a single frame.
Everything else is treated as a video and frames are extracted with cv2.
"""

import logging
import math
import os
import random
import tempfile
from pathlib import Path
from statistics import mean, stdev

logger = logging.getLogger(__name__)

# ── Engine detection ──────────────────────────────────────────────────────────

_CV2_AVAILABLE  = False
_MP_AVAILABLE   = False
_FACE_CASCADE   = None          # lazy-loaded OpenCV Haar Cascade

try:
    import cv2                  # type: ignore
    import numpy as np          # type: ignore
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
    """Lazy-load the OpenCV Haar Cascade (bundled with cv2)."""
    global _FACE_CASCADE
    if _FACE_CASCADE is None and _CV2_AVAILABLE:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _FACE_CASCADE = cv2.CascadeClassifier(path)
    return _FACE_CASCADE


# ── Frame result data model (plain dict for speed) ───────────────────────────
# { has_face, cx, cy, size, center_dist }
#   cx / cy      — relative [0,1] centre of detected face
#   size         — relative area of face bounding box
#   center_dist  — Euclidean distance from frame centre (0=perfect, 0.5=edge)

_MISS = {"has_face": False, "cx": 0.5, "cy": 0.5, "size": 0.0, "center_dist": 0.5}


# ── Frame analysers ───────────────────────────────────────────────────────────

def _face_info_haar(frame_bgr) -> dict:
    cascade = _get_face_cascade()
    gray    = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces   = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
    if not len(faces):
        return _MISS.copy()
    h, w   = frame_bgr.shape[:2]
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])  # largest face
    cx     = (x + fw / 2) / w
    cy     = (y + fh / 2) / h
    size   = (fw * fh) / (w * h)
    return {"has_face": True, "cx": cx, "cy": cy, "size": size,
            "center_dist": math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2)}


def _face_info_mediapipe(frame_bgr, detector) -> dict:
    rgb     = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result  = detector.process(rgb)
    if not result.detections:
        return _MISS.copy()
    det    = result.detections[0]           # highest-confidence detection
    bb     = det.location_data.relative_bounding_box
    cx     = bb.xmin + bb.width  / 2
    cy     = bb.ymin + bb.height / 2
    size   = bb.width * bb.height
    return {"has_face": True, "cx": cx, "cy": cy, "size": size,
            "center_dist": math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2)}


# ── Score computation from frame results ──────────────────────────────────────

def _scores_from_frames(frame_data: list[dict]) -> dict:
    total     = len(frame_data)
    if total == 0:
        return dict(engagement_score=60, eye_contact_score=60,
                    posture_score=65, stress_indicator="medium",
                    face_detection_rate=0.0)

    with_face        = [f for f in frame_data if f["has_face"]]
    detection_rate   = len(with_face) / total

    # ── Engagement: how often face is present ─────────────────────────────────
    # 100 % presence → ~95; 0 % → 20
    engagement = int(max(20, min(95, detection_rate * 75 + 20)))

    # ── Eye contact: face centred in frame ───────────────────────────────────
    if with_face:
        avg_dist   = mean(f["center_dist"] for f in with_face)
        # avg_dist = 0 → perfectly centred (100); avg_dist = 0.5 → at edge (~20)
        eye_contact = int(max(20, min(95, 95 - avg_dist * 140)))
    else:
        eye_contact = 25

    # ── Posture: stable face size across frames ──────────────────────────────
    if len(with_face) >= 3:
        sizes       = [f["size"] for f in with_face]
        size_std    = stdev(sizes)
        posture     = int(max(20, min(95, 88 - size_std * 350)))
    elif len(with_face) >= 1:
        posture = 68
    else:
        posture = 45

    # ── Stress: frame-to-frame head movement ─────────────────────────────────
    if len(with_face) >= 4:
        movements = [
            math.sqrt((with_face[i]["cx"] - with_face[i-1]["cx"]) ** 2
                    + (with_face[i]["cy"] - with_face[i-1]["cy"]) ** 2)
            for i in range(1, len(with_face))
        ]
        avg_move = mean(movements)
        if avg_move > 0.06:
            stress = "high"
        elif avg_move > 0.025:
            stress = "medium"
        else:
            stress = "low"
    elif detection_rate < 0.4:
        stress = "high"     # rarely in frame → anxious / distracted
    elif detection_rate < 0.7:
        stress = "medium"
    else:
        stress = "low"

    return dict(
        engagement_score   = engagement,
        eye_contact_score  = eye_contact,
        posture_score      = posture,
        stress_indicator   = stress,
        face_detection_rate= round(detection_rate, 3),
    )


# ── Frame extraction from video ───────────────────────────────────────────────

def _extract_frames(video_path: str, max_frames: int = 30) -> list:
    cap    = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step   = max(1, total // max_frames)
    frames = []
    idx    = 0
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


# ── OpenCV + MediaPipe analyser ───────────────────────────────────────────────

def _analyze_opencv_mediapipe(frames: list) -> dict:
    mp_face = mp.solutions.face_detection        # type: ignore[reportPossiblyUnbound]
    frame_data = []
    with mp_face.FaceDetection(min_detection_confidence=0.5) as detector:
        for frame in frames:
            frame_data.append(_face_info_mediapipe(frame, detector))
    scores = _scores_from_frames(frame_data)
    scores.update(mode="opencv_mediapipe", frames_analyzed=len(frames))
    return scores


# ── OpenCV-only analyser ──────────────────────────────────────────────────────

def _analyze_opencv(frames: list) -> dict:
    frame_data = [_face_info_haar(f) for f in frames]
    scores     = _scores_from_frames(frame_data)
    scores.update(mode="opencv", frames_analyzed=len(frames))
    return scores


# ── Fallback analyser ─────────────────────────────────────────────────────────

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

def _analyze_fallback(file_bytes: bytes, is_image: bool) -> dict:
    """
    Heuristic scores when computer-vision libraries are unavailable.

    Video: webcam webm ≈ 800 KB/s → duration → frame count estimate.
    Image: single-frame capture → treat as short clip.
    Scores are seeded from file_size for reproducibility.
    """
    file_size = len(file_bytes)
    rng       = random.Random(file_size % 99_991)

    if is_image:
        duration_s   = 2.0       # treat snapshot as a ~2-second clip
        frame_est    = 5
    else:
        # webcam webm (360p–720p) ≈ 600 KB/s
        duration_s   = max(1.0, file_size / 600_000.0)
        frame_est    = max(5, int(duration_s * 30 / 15))   # sample every 15th frame

    # Base scores: assume decent interview setup
    engagement  = int(max(30, min(92, 78 + rng.randint(-10, 10))))
    eye_contact = int(max(30, min(90, 72 + rng.randint(-10, 10))))
    posture     = int(max(30, min(90, 75 + rng.randint(-8,   8))))

    # Stress: short clips → can't tell, default medium
    stress_choice = rng.random()
    if stress_choice > 0.70:
        stress = "low"
    elif stress_choice > 0.25:
        stress = "medium"
    else:
        stress = "high"

    face_rate = round(min(1.0, max(0.3, 0.80 + rng.uniform(-0.2, 0.15))), 2)

    return dict(
        engagement_score   = engagement,
        eye_contact_score  = eye_contact,
        posture_score      = posture,
        stress_indicator   = stress,
        mode               = "fallback",
        frames_analyzed    = frame_est,
        face_detection_rate= face_rate,
    )


# ── Public entry point ────────────────────────────────────────────────────────

async def analyze(file_bytes: bytes, filename: str = "capture.webm") -> dict:
    """
    Accepts raw bytes (video or image) and returns a VideoAnalysisResponse dict.
    Writes to a temp file only when CV2 is available to extract frames.
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

        # ── Obtain frames ─────────────────────────────────────────────────────
        if is_image:
            frame = _bytes_to_frame(file_bytes)
            frames = [frame] if frame is not None else []
        else:
            frames = _extract_frames(tmp.name, max_frames=30)

        if not frames:
            logger.warning("Video analyser: no frames extracted — using fallback.")
            return _analyze_fallback(file_bytes, is_image)

        # ── Run best available engine ─────────────────────────────────────────
        if _MP_AVAILABLE:
            return _analyze_opencv_mediapipe(frames)
        else:
            return _analyze_opencv(frames)

    except Exception as exc:
        logger.warning("Video analysis failed (%s) — using fallback: %s",
                       "mediapipe" if _MP_AVAILABLE else "opencv", exc)
        return _analyze_fallback(file_bytes, is_image)

    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
