from pydantic import BaseModel
from typing import List, Optional


class VideoAnalysisResponse(BaseModel):
    # Analysis validity
    status:              str                      # "ok" | "invalid_analysis"
    reason:              Optional[str]  = None    # human-readable reason when status=invalid_analysis

    # Core scores (None when status=invalid_analysis or insufficient data)
    engagement_score:    Optional[int]  = None    # 0-100  face presence rate
    framing_score:       Optional[int]  = None    # 0-100  face centering in frame (centering proxy)
    stability_score:     Optional[int]  = None    # 0-100  face-size consistency (distance proxy)
                                                  #        None when < 3 valid face frames
    movement_activity:   Optional[str]  = None    # "low" | "medium" | "high"  head-movement intensity

    # Engine metadata
    mode:                str                      # opencv_mediapipe | opencv | fallback
    frames_analyzed:     Optional[int]  = None
    face_detection_rate: Optional[float] = None   # 0.0-1.0

    # Explainability
    analysis_notes:      Optional[List[str]] = None   # per-metric human-readable notes
    warning:             Optional[str]  = None         # e.g. "Not enough frames for stability"
    face_presence:       Optional[bool] = None
    face_presence_score: Optional[int] = None
    eye_contact_proxy:   Optional[int]  = None
    facial_expression_proxy: Optional[str] = None
    posture_proxy:       Optional[int]  = None
    stress_nervousness_indicator: Optional[str] = None
    nervousness_score:   Optional[int] = None
    metrics_source:      str = "heuristic"

    # ── Orchestrator guidance (new) ───────────────────────────────────────────
    # Explicit nervousness proxy (0-100, higher = more nervous).
    # Derived from movement_activity + framing instability + low engagement.
    nervousness_proxy_score: Optional[int] = None

    # Looking-away proxy (0-100, lower = more eye-contact-like framing).
    # Derived from framing_score inversion.
    looking_away_proxy_score: Optional[int] = None

    # Plain-English narrative describing the full video analysis result.
    visual_reasoning_summary: Optional[str] = None

    # Machine-readable hint for the intelligence engine / orchestrator.
    recommendation_to_orchestrator: Optional[str] = None
