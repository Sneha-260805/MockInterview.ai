from pydantic import BaseModel
from typing import Optional


class AudioAnalysisResponse(BaseModel):
    transcript: str
    confidence_score: int               # 0-100
    communication_clarity_score: int    # 0-100
    pause_count: int
    speaking_rate: str                  # slow | medium | fast
    mode: str                           # faster_whisper | whisper | fallback
    word_count: Optional[int] = None
    duration_seconds: Optional[float] = None
