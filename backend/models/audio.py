from pydantic import BaseModel, Field
from typing import List, Optional


class AudioAnalysisResponse(BaseModel):
    # Analysis status
    status: str = "ok"                         # "ok" | "invalid_audio"
    reason: Optional[str] = None               # set when status == "invalid_audio"

    # Core transcript
    transcript: str

    # Primary scores (0-100)
    confidence_score: int
    communication_clarity_score: int

    # Speech metrics
    pause_count: int
    speaking_rate: str                         # "slow" | "medium" | "fast"
    words_per_minute: Optional[float] = None

    # Filler-word analysis
    filler_word_count: Optional[int] = None
    filler_ratio: Optional[float] = None       # 0.0–1.0

    # Hesitation classification
    hesitation_level: Optional[str] = None    # "low" | "moderate" | "high"

    # Pitch analysis (librosa; "unavailable" when librosa not installed)
    pitch_stability: Optional[str] = None     # "stable" | "variable" | "monotone" | "unavailable"

    # Plain-English explainability notes
    analysis_notes: List[str] = Field(default_factory=list)

    # Engine & metadata
    mode: str                                  # "faster_whisper" | "whisper" | "fallback"
    word_count: Optional[int] = None
    duration_seconds: Optional[float] = None
