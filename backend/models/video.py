from pydantic import BaseModel
from typing import Optional


class VideoAnalysisResponse(BaseModel):
    engagement_score:  int    # 0-100  face present + attentive
    eye_contact_score: int    # 0-100  face centred in frame
    posture_score:     int    # 0-100  stable, upright position
    stress_indicator:  str    # low | medium | high
    mode:              str    # opencv_mediapipe | opencv | fallback
    frames_analyzed:       Optional[int]   = None
    face_detection_rate:   Optional[float] = None   # 0.0-1.0
