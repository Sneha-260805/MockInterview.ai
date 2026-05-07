"""
Phase 8 — Audio Intelligence analyser.

Analyses a voice-recording bytes buffer and returns:
  transcript                    — text of what was said
  confidence_score              — 0-100 (pauses, fluency)
  communication_clarity_score   — 0-100 (pace, length)
  pause_count                   — long silences (> 500 ms)
  speaking_rate                 — "slow" | "medium" | "fast"
  mode                          — "faster_whisper" | "whisper" | "fallback"

Engine priority:
  1. faster-whisper (pip install faster-whisper)
  2. openai-whisper  (pip install openai-whisper)
  3. Fallback        — no install needed; uses file-size as duration proxy
                       and produces plausible demo scores for hackathon use.
"""

import logging
import math
import os
import random
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Detect available transcription engine ─────────────────────────────────────

_ENGINE: str = "fallback"
_model_instance = None

try:
    from faster_whisper import WhisperModel as _FasterWhisperModel  # type: ignore
    _ENGINE = "faster_whisper"
    logger.info("Audio analyser: faster-whisper detected.")
except ImportError:
    try:
        import whisper as _openai_whisper  # type: ignore
        _ENGINE = "whisper"
        logger.info("Audio analyser: openai-whisper detected.")
    except ImportError:
        logger.info(
            "Audio analyser: no Whisper library found — using fallback scoring. "
            "Install faster-whisper for real transcription: pip install faster-whisper"
        )


def _get_model():
    """Lazy-load the Whisper model on first use."""
    global _model_instance
    if _model_instance is None:
        if _ENGINE == "faster_whisper":
            from faster_whisper import WhisperModel
            logger.info("Loading faster-whisper 'base' model (CPU, int8)…")
            _model_instance = WhisperModel("base", device="cpu", compute_type="int8")
        elif _ENGINE == "whisper":
            import whisper as _w
            logger.info("Loading openai-whisper 'base' model…")
            _model_instance = _w.load_model("base")
    return _model_instance


# ── Speaking-rate → wpm helper ────────────────────────────────────────────────

def _wpm_to_rate(wpm: float) -> str:
    if wpm < 100:
        return "slow"
    if wpm > 165:
        return "fast"
    return "medium"


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _score_confidence(pause_count: int, duration_sec: float) -> int:
    """Confidence falls as pause frequency rises."""
    pause_rate = pause_count / max(duration_sec / 60.0, 0.1)  # pauses per minute
    return max(25, min(95, 80 - int(pause_rate * 3)))


def _score_clarity(speaking_rate: str, word_count: int) -> int:
    """
    Clarity peaks at medium pace (natural, measured delivery).
    Very short answers and fast-clipped speech reduce clarity.
    """
    base = {"medium": 82, "slow": 66, "fast": 72}.get(speaking_rate, 75)
    if word_count < 20:
        base -= 22
    elif word_count < 50:
        base -= 10
    return max(25, min(95, base))


# ── Fallback analyser ─────────────────────────────────────────────────────────

def _analyze_fallback(file_bytes: bytes) -> dict:
    """
    Produces plausible scores when Whisper is unavailable.

    Duration is estimated from file size:
        webm/opus voice ≈ 16 kbps ≈ 2 000 bytes / second

    The RNG is seeded from file_size so the same recording always
    gets the same scores (reproducible for demo runs).
    """
    file_size   = len(file_bytes)
    duration_s  = max(2.0, file_size / 2_000.0)
    rng         = random.Random(file_size % 99_991)  # prime → better spread

    # Speaking rate from duration
    if duration_s < 15:
        speaking_rate, wpm_est = "fast",   175
    elif duration_s < 90:
        speaking_rate, wpm_est = "medium", 130
    else:
        speaking_rate, wpm_est = "slow",    95

    word_count_est = max(5, int(duration_s * wpm_est / 60))
    pause_count    = max(0, int(duration_s / 15) + rng.randint(-1, 2))

    confidence = _score_confidence(pause_count, duration_s)
    confidence = int(max(30, min(93, confidence + rng.randint(-6, 10))))

    clarity    = _score_clarity(speaking_rate, word_count_est)
    clarity    = int(max(30, min(92, clarity  + rng.randint(-5,  8))))

    transcript = (
        f"[Audio recorded — ~{int(duration_s)}s, ~{word_count_est} words estimated. "
        "Install faster-whisper for live transcription: pip install faster-whisper]"
    )

    return {
        "transcript":                  transcript,
        "confidence_score":            confidence,
        "communication_clarity_score": clarity,
        "pause_count":                 pause_count,
        "speaking_rate":               speaking_rate,
        "mode":                        "fallback",
        "word_count":                  word_count_est,
        "duration_seconds":            round(duration_s, 1),
    }


# ── faster-whisper analyser ───────────────────────────────────────────────────

def _analyze_faster_whisper(audio_path: str) -> dict:
    model        = _get_model()
    segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=False)
    seg_list     = list(segments)

    transcript   = " ".join(s.text.strip() for s in seg_list).strip() or "[No speech detected]"
    duration_s   = max(info.duration, 0.01)
    word_count   = len(transcript.split()) if transcript.strip() else 0

    speaking_rate = _wpm_to_rate((word_count / duration_s) * 60)

    pause_count = sum(
        1
        for i in range(1, len(seg_list))
        if seg_list[i].start - seg_list[i - 1].end > 0.5
    )

    return {
        "transcript":                  transcript,
        "confidence_score":            _score_confidence(pause_count, duration_s),
        "communication_clarity_score": _score_clarity(speaking_rate, word_count),
        "pause_count":                 pause_count,
        "speaking_rate":               speaking_rate,
        "mode":                        "faster_whisper",
        "word_count":                  word_count,
        "duration_seconds":            round(duration_s, 1),
    }


# ── openai-whisper analyser ───────────────────────────────────────────────────

def _analyze_openai_whisper(audio_path: str) -> dict:
    model      = _get_model()
    result     = model.transcribe(audio_path)
    transcript = result.get("text", "").strip() or "[No speech detected]"
    segments   = result.get("segments", [])
    duration_s = max(result.get("duration", 1.0), 0.01)
    word_count = len(transcript.split()) if transcript.strip() else 0

    speaking_rate = _wpm_to_rate((word_count / duration_s) * 60)

    pause_count = sum(
        1
        for i in range(1, len(segments))
        if segments[i]["start"] - segments[i - 1]["end"] > 0.5
    )

    return {
        "transcript":                  transcript,
        "confidence_score":            _score_confidence(pause_count, duration_s),
        "communication_clarity_score": _score_clarity(speaking_rate, word_count),
        "pause_count":                 pause_count,
        "speaking_rate":               speaking_rate,
        "mode":                        "whisper",
        "word_count":                  word_count,
        "duration_seconds":            round(duration_s, 1),
    }


# ── Public entry point ────────────────────────────────────────────────────────

async def analyze(file_bytes: bytes, filename: str = "audio.webm") -> dict:
    """
    Accepts raw audio bytes, writes to a temp file, analyses, cleans up.
    Always returns a dict matching AudioAnalysisResponse fields.
    Falls back gracefully if the Whisper engine fails at runtime.
    """
    if _ENGINE == "fallback":
        return _analyze_fallback(file_bytes)

    suffix = Path(filename).suffix or ".webm"
    tmp    = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(file_bytes)
        tmp.flush()
        tmp.close()

        if _ENGINE == "faster_whisper":
            return _analyze_faster_whisper(tmp.name)
        else:
            return _analyze_openai_whisper(tmp.name)

    except Exception as exc:
        logger.warning(
            "Whisper analysis failed (%s) — falling back to heuristics: %s", _ENGINE, exc
        )
        return _analyze_fallback(file_bytes)

    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
