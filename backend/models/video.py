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
