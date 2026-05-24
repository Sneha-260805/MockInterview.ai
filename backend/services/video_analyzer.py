"""
Phase 9 — Video Intelligence analyser (improved heuristics).

Accepts either a short video clip (webm/mp4) or a single JPEG/PNG frame
and returns:
    engagement_score   — 0-100  face presence rate (honest proxy)
    framing_score      — 0-100  face centred in frame (centering proxy for eye contact)
    stability_score    — 0-100  face-size variance across frames (distance stability)
                                None when fewer than 3 valid frames exist
    movement_activity  — "low" | "medium" | "high"  head-movement / nervousness indicator
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

Invalid analysis gate (any condition triggers it)
──────────────────────────────────────────────────
• face_detection_rate < 0.35 after excluding passerby intrusions
• fewer than 3 candidate face detections
• longest gap of consecutive no-face frames > 14 sampled frames
  (≈ 7 s in a 15 s clip at 30 fps sampled every 15th frame)

Passerby / disturbance handling
────────────────────────────────
• When multiple faces are detected in a frame the one closest to the
  frame centre is chosen as the candidate (the interviewee sits centred).
• Any frame where the chosen face area exceeds 2.8× the median candidate
  face area is marked as a "passerby intrusion" and excluded from scoring
  (a person walking close to the camera produces an abnormally large bbox).

Score calibration targets
─────────────────────────
Poor session:    15–40
Average session: 50–70
Strong session:  75–90
"""

import asyncio
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

_MIN_DETECTION_RATE  = 0.35   # below this → invalid_analysis (raised from 0.30)
_MIN_VALID_FACES     = 3      # fewer face detections → stability_score = None
_MAX_INVALID_GAP     = 14     # longest consecutive no-face streak above this → invalid
_PASSERBY_AREA_RATIO = 2.8    # face area > ratio × median → passerby, excluded from scores

# ── Frame result dict:
#   has_face, cx, cy, size, center_dist  (all positions in [0, 1] relative coords)

_MISS = {
    "has_face": False,
    "cx": 0.5,
    "cy": 0.5,
    "size": 0.0,
    "center_dist": 0.5,
    "edge_margin": 0.0,
}


# ── Per-frame face detectors ──────────────────────────────────────────────────

def _face_info_haar(frame_bgr) -> dict:
    cascade = _get_face_cascade()
    gray    = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces   = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
    if not len(faces):
        return _MISS.copy()
    h, w = frame_bgr.shape[:2]
    # Pick the face closest to the frame centre (candidate sits centred; passersby are at edges)
    def _centre_dist(f):
        return ((f[0] + f[2] / 2) / w - 0.5) ** 2 + ((f[1] + f[3] / 2) / h - 0.5) ** 2
    x, y, fw, fh = min(faces, key=_centre_dist)
    cx   = (x + fw / 2) / w
    cy   = (y + fh / 2) / h
    size = (fw * fh) / (w * h)
    left, top, right, bottom = x / w, y / h, (x + fw) / w, (y + fh) / h
    edge_margin = min(left, top, 1 - right, 1 - bottom)
    return {"has_face": True, "cx": cx, "cy": cy, "size": size,
            "center_dist": math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2),
            "edge_margin": edge_margin}


def _face_info_mediapipe(frame_bgr, detector) -> dict:
    rgb    = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = detector.process(rgb)
    if not result.detections:
        return _MISS.copy()
    # When multiple faces present (passerby walked into frame), pick the one
    # closest to the frame centre — the candidate sits directly in front of the camera.
    best, best_sq = None, float("inf")
    for det in result.detections:
        bb  = det.location_data.relative_bounding_box
        fcx = bb.xmin + bb.width  / 2
        fcy = bb.ymin + bb.height / 2
        sq  = (fcx - 0.5) ** 2 + (fcy - 0.5) ** 2
        if sq < best_sq:
            best_sq, best = sq, det
    bb   = best.location_data.relative_bounding_box
    cx   = bb.xmin + bb.width  / 2
    cy   = bb.ymin + bb.height / 2
    size = bb.width * bb.height
    edge_margin = min(bb.xmin, bb.ymin, 1 - (bb.xmin + bb.width), 1 - (bb.ymin + bb.height))
    return {"has_face": True, "cx": cx, "cy": cy, "size": size,
            "center_dist": math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2),
            "edge_margin": edge_margin}


# ── Orchestrator guidance helper ──────────────────────────────────────────────

def _compute_video_extras(
    engagement: Optional[int],
    framing: Optional[int],
    stability: Optional[int],
    movement: Optional[str],
    detection_rate: float,
) -> dict:
    """
    Derive orchestrator guidance fields from already-computed video scores.
    Safe to call for invalid_analysis paths — returns None for derived scores.

    nervousness_proxy_score  (0-100, higher = more nervous indicators)
      Combines high movement + poor framing + low engagement.

    looking_away_proxy_score (0-100, lower = more eye-contact-like framing)
      Simple inversion of framing_score.

    visual_reasoning_summary — plain-English narrative for UI / final report.

    recommendation_to_orchestrator — machine-readable hint for the intelligence engine.
    """
    # ── Nervousness proxy ──────────────────────────────────────────────────────
    if engagement is None or framing is None:
        nervousness_proxy: Optional[int] = None
    else:
        movement_penalty   = {"high": 35, "medium": 15, "low": 0}.get(movement or "low", 0)
        framing_penalty    = max(0, (50 - framing)) // 2      # low framing → more nervous
        engagement_penalty = max(0, (50 - engagement)) // 2   # low engagement → more nervous
        nervousness_proxy  = int(min(100, max(0,
            movement_penalty + framing_penalty + engagement_penalty)))

    # ── Looking-away proxy ─────────────────────────────────────────────────────
    looking_away_proxy: Optional[int] = (100 - framing) if framing is not None else None

    # ── Visual reasoning summary ───────────────────────────────────────────────
    if engagement is None:
        visual_summary = (
            "Visual analysis could not be completed — face was not consistently "
            "visible. Ensure your face is well-lit and centred in the camera frame."
        )
    else:
        eng_desc   = ("strong" if engagement >= 75 else
                      "adequate" if engagement >= 55 else "limited") + " camera presence"
        frame_desc = ("well-centred" if (framing or 0) >= 70 else
                      "acceptable" if (framing or 0) >= 50 else "off-centre") + " framing"
        if stability is None:
            stab_desc = "insufficient data for stability analysis"
        elif stability >= 70:
            stab_desc = "stable camera distance"
        elif stability >= 50:
            stab_desc = "moderate distance variation"
        else:
            stab_desc = "significant movement or distance changes"
        move_desc = (
            "High head movement was detected, which may indicate nervousness." if movement == "high"
            else "Moderate head movement observed." if movement == "medium"
            else "Physical composure was good with minimal head movement."
        )
        visual_summary = (
            f"Video analysis shows {eng_desc}, {frame_desc}, and {stab_desc}. {move_desc}"
        )

    # ── Recommendation to orchestrator ─────────────────────────────────────────
    if engagement is None:
        rec = "request_better_video_setup"
    elif nervousness_proxy is not None and nervousness_proxy >= 60:
        rec = "acknowledge_nervousness_and_encourage"
    elif engagement < 40 and (framing is None or framing < 40):
        rec = "request_better_video_setup"
    elif nervousness_proxy is not None and nervousness_proxy >= 35:
        rec = "note_nervousness_monitor_confidence"
    else:
        rec = "no_video_action_needed"

    return {
        "nervousness_proxy_score":        nervousness_proxy,
        "looking_away_proxy_score":       looking_away_proxy,
        "visual_reasoning_summary":       visual_summary,
        "recommendation_to_orchestrator": rec,
    }


# ── Score computation ─────────────────────────────────────────────────────────

def _scores_from_frames(frame_data: list[dict]) -> dict:
    """
    Compute all video scores from per-frame face detection results.

    Invalid analysis is returned when ANY of these conditions hold:
      • no frames extracted
      • longest consecutive no-face streak > _MAX_INVALID_GAP (candidate left / camera blocked)
      • candidate face detection rate < _MIN_DETECTION_RATE after passerby exclusion
      • fewer than _MIN_VALID_FACES clean candidate frames

    Passerby intrusion filtering:
      Frames where the selected (most-central) face area exceeds
      _PASSERBY_AREA_RATIO × median area are treated as contaminated and
      excluded from all score calculations.
    """
    total = len(frame_data)
    if total == 0:
        extras = _compute_video_extras(None, None, None, None, 0.0)
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
            **extras,
        }

    # ── Gap analysis: detect camera-blocked / candidate-left-frame ────────────
    presence = [f["has_face"] for f in frame_data]
    max_gap  = cur_gap = 0
    for present in presence:
        if not present:
            cur_gap += 1
            max_gap  = max(max_gap, cur_gap)
        else:
            cur_gap = 0

    if max_gap > _MAX_INVALID_GAP:
        extras = _compute_video_extras(None, None, None, None, round(sum(presence) / total, 3))
        return {
            "status": "invalid_analysis",
            "reason": (
                f"No face detected for {max_gap} consecutive frames — the camera was "
                "blocked or you left the frame for an extended period. "
                "Record in a stable, uninterrupted environment."
            ),
            "engagement_score":    None,
            "framing_score":       None,
            "stability_score":     None,
            "movement_activity":   None,
            "face_detection_rate": round(sum(presence) / total, 3),
            "analysis_notes":      [],
            "warning":             None,
            **extras,
        }

    # ── Passerby intrusion filter ─────────────────────────────────────────────
    # A person walking very close to the camera produces a face bbox far larger
    # than the candidate's.  Exclude frames where face area > ratio × median.
    raw_with_face = [f for f in frame_data if f["has_face"]]
    if len(raw_with_face) >= 3:
        sorted_sizes  = sorted(f["size"] for f in raw_with_face)
        median_size   = sorted_sizes[len(sorted_sizes) // 2]
        area_ceiling  = median_size * _PASSERBY_AREA_RATIO
        with_face     = [f for f in raw_with_face if f["size"] <= area_ceiling]
        passerby_cnt  = len(raw_with_face) - len(with_face)
    else:
        with_face    = raw_with_face
        passerby_cnt = 0

    detection_rate = len(with_face) / total

    # ── Invalid analysis gate ─────────────────────────────────────────────────
    if detection_rate < _MIN_DETECTION_RATE or len(with_face) < _MIN_VALID_FACES:
        if len(with_face) < _MIN_VALID_FACES:
            reason = (
                f"Only {len(with_face)} usable frame(s) with a detected face — "
                "too few for reliable analysis. Ensure good lighting and "
                "that your face is clearly visible throughout the recording."
            )
        else:
            pct = round(detection_rate * 100)
            reason = (
                f"Candidate face detected in only {pct}% of frames "
                f"(threshold: {round(_MIN_DETECTION_RATE * 100)}%). "
            )
            if passerby_cnt:
                reason += (
                    f"{passerby_cnt} frame(s) were excluded due to background intrusion. "
                )
            if max_gap > 5:
                reason += (
                    f"The longest gap without a face was {max_gap} frames. "
                )
            reason += "Try recording alone in a quiet space facing the camera directly."
        extras = _compute_video_extras(None, None, None, None, round(detection_rate, 3))
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
            **extras,
        }

    notes: list[str] = []
    if passerby_cnt:
        notes.append(
            f"Background intrusion detected in {passerby_cnt} frame(s) — "
            "excluded from scoring. Scores reflect candidate visibility only."
        )
    if max_gap > 5:
        notes.append(
            f"Longest gap without a face: {max_gap} sampled frames — "
            "try to keep your face visible throughout."
        )

    # ── Framing: face centred in frame (outlier-filtered) ─────────────────────
    dists      = sorted(f["center_dist"] for f in with_face)
    trim_count = max(1, int(len(dists) * 0.90))   # keep best 90%
    avg_dist   = mean(dists[:trim_count])
    framing    = int(max(15, min(88, 88 - avg_dist * 165)))

    edge_margins = sorted(f.get("edge_margin", 0.0) for f in with_face)
    avg_edge_margin = mean(edge_margins[:trim_count])
    is_edge_cropped = avg_edge_margin < 0.025
    is_poorly_framed = avg_dist >= 0.24

    # ── Engagement: face presence plus usable frame quality ───────────────────
    # A face detected at the edge of the frame should not look "high engagement".
    # Good: 80-88. Poorly framed/cropped: capped to 35-58 even with high detection.
    usable_frame_quality = max(0.0, min(1.0, 1 - avg_dist * 2.2))
    if is_edge_cropped:
        usable_frame_quality *= 0.45
    engagement = int(max(15, min(88, 15 + detection_rate * 35 + usable_frame_quality * 38)))
    if is_edge_cropped:
        engagement = min(engagement, 45)
    elif is_poorly_framed:
        engagement = min(engagement, 58)

    if detection_rate < 0.60:
        notes.append("Frequent face loss detected — check lighting and camera angle.")
    elif is_edge_cropped:
        notes.append("Face was detected but often cropped at the frame edge — keep your full face visible.")
    elif is_poorly_framed:
        notes.append("Face was visible but poorly framed — center your face before recording.")
    elif detection_rate >= 0.85:
        notes.append("Face remained consistently visible throughout.")
    else:
        notes.append("Face was visible in most frames.")

    if is_edge_cropped:
        framing = min(framing, 35)
        notes.append("Face was too close to the edge of the camera view.")
    elif avg_dist < 0.08:
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
        if is_edge_cropped:
            stability = min(stability, 45)
        elif is_poorly_framed:
            stability = min(stability, 65)

        if is_edge_cropped:
            notes.append("Stability is reduced because the face was partially outside the frame.")
        elif is_poorly_framed:
            notes.append("Stability is limited because the camera framing was poor.")
        elif size_std < 0.025:
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

    extras = _compute_video_extras(engagement, framing, stability, movement, round(detection_rate, 3))
    return {
        "status":              "ok",
        "engagement_score":    engagement,
        "framing_score":       framing,
        "stability_score":     stability,
        "movement_activity":   movement,
        "face_detection_rate": round(detection_rate, 3),
        "analysis_notes":      notes,
        "warning":             warning,
        **extras,
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

    extras = _compute_video_extras(engagement, framing, None, movement, face_rate)
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
        "face_presence": True,
        "face_presence_score": engagement,
        "eye_contact_proxy": framing,
        "facial_expression_proxy": "unavailable",
        "posture_proxy": None,
        "stress_nervousness_indicator": movement,
        "nervousness_score": 35 if movement == "low" else 60 if movement == "medium" else 82,
        "metrics_source": "heuristic",
        **extras,
    }


# ── Public entry point ────────────────────────────────────────────────────────

async def analyze(file_bytes: bytes, filename: str = "capture.webm") -> dict:
    """
    Accepts raw bytes (video or image) and returns a VideoAnalysisResponse dict.
    Writes to a temp file only when cv2 is available to extract frames.
    Always cleans up the temp file.
    Falls back gracefully if any engine step fails.

    OpenCV frame extraction and MediaPipe inference are CPU-bound and
    synchronous.  Both are offloaded to the default ThreadPoolExecutor so
    the FastAPI event loop stays free, enabling audio + video to run truly
    in parallel via asyncio.gather().
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

        loop = asyncio.get_event_loop()

        if is_image:
            # _bytes_to_frame is fast — no need to offload
            frame  = _bytes_to_frame(file_bytes)
            frames = [frame] if frame is not None else []
        else:
            # Frame extraction reads the whole video — offload to thread pool
            frames = await loop.run_in_executor(
                None, lambda: _extract_frames(tmp.name, max_frames=15)
            )

        if not frames:
            logger.warning("Video analyser: no frames extracted — using fallback.")
            return _analyze_fallback(file_bytes, is_image)

        # Face detection / scoring — offload heavy inference to thread pool
        if _MP_AVAILABLE:
            return await loop.run_in_executor(None, _analyze_opencv_mediapipe, frames)
        else:
            return await loop.run_in_executor(None, _analyze_opencv, frames)

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
