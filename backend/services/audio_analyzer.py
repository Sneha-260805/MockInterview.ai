"""
Phase 8 — Audio Intelligence analyser (improved).

Analyses a voice-recording bytes buffer and returns:
  status                        — "ok" | "invalid_audio"
  transcript                    — text of what was said
  confidence_score              — 0-100 (hesitation, fillers, pace)
  communication_clarity_score   — 0-100 (structure, completeness, fluency)
  pause_count                   — long silences (> 500 ms)
  speaking_rate                 — "slow" | "medium" | "fast"
  words_per_minute              — calculated WPM
  filler_word_count             — occurrences of "um", "uh", "like", etc.
  filler_ratio                  — filler_count / total_words
  hesitation_level              — "low" | "moderate" | "high"
  pitch_stability               — "stable" | "variable" | "monotone" | "unavailable"
  analysis_notes                — list of plain-English observations
  reason                        — set when status == "invalid_audio"
  mode                          — "faster_whisper" | "whisper" | "fallback"

Engine priority:
  1. faster-whisper  (pip install faster-whisper)   ← recommended
  2. openai-whisper  (pip install openai-whisper)
  3. Fallback        — file-size heuristics; conservative scores

Optional pitch analysis:
  pip install librosa            ← enables pitch stability detection
"""

import asyncio
import logging
import os
import random
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Engine detection ───────────────────────────────────────────────────────────

_ENGINE: str = "fallback"
_model_instance = None

_REAL_TRANSCRIPTION_ENABLED = os.getenv("ENABLE_REAL_AUDIO_TRANSCRIPTION", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if _REAL_TRANSCRIPTION_ENABLED:
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
                "Audio analyser: no Whisper library found - using fallback scoring. "
                "Install faster-whisper for real transcription: pip install faster-whisper"
            )
else:
    logger.info(
        "Audio analyser: real transcription disabled; using fast heuristic scoring. "
        "Set ENABLE_REAL_AUDIO_TRANSCRIPTION=true to enable Whisper transcription."
    )

# ── Optional: librosa for pitch analysis ──────────────────────────────────────

_HAS_LIBROSA = False
try:
    import librosa  # type: ignore
    import numpy as np  # type: ignore
    _HAS_LIBROSA = True
    logger.info("Audio analyser: librosa detected — pitch stability analysis enabled.")
except ImportError:
    logger.info(
        "Audio analyser: librosa not found — pitch analysis disabled. "
        "pip install librosa to enable pitch stability detection."
    )

# ── Thresholds ─────────────────────────────────────────────────────────────────

# Filler words: single-word terms that commonly appear as speech fillers
FILLER_WORDS = frozenset({
    "um", "uh", "hmm", "uhh", "umm",
    "basically", "literally", "actually",
    "so", "well", "right", "okay", "ok",
    "like",  # counted as filler when frequency is high
})

FILLER_PHRASES = (
    "you know",
    "i mean",
    "kind of",
    "sort of",
)

MIN_WORDS_FOR_ANALYSIS  = 8      # fewer words → invalid_audio
MIN_DURATION_SECONDS    = 3.0    # shorter clip → invalid_audio

WPM_FAST_THRESHOLD = 175         # > 175 wpm → "fast"
WPM_SLOW_THRESHOLD = 95          # < 95 wpm  → "slow"

PAUSE_THRESHOLD_S  = 0.5         # gap > 500 ms counts as a pause
PAUSE_RATE_HIGH    = 5.0         # pauses/min → high hesitation
PAUSE_RATE_MOD     = 2.0         # pauses/min → moderate hesitation

FILLER_RATIO_HIGH  = 0.10        # ≥ 10 % of words are fillers → high
FILLER_RATIO_MOD   = 0.05        # ≥ 5 %                       → moderate

# Pitch coefficient-of-variation boundaries
PITCH_CV_VARIABLE  = 0.45        # CV > 0.45 → variable (high)
PITCH_CV_MONOTONE  = 0.12        # CV < 0.12 → monotone (flat)

WHISPER_MODEL_NAME = os.getenv("AUDIO_TRANSCRIPTION_MODEL", "tiny")

# Base timeout (lower-bound).  For longer recordings the timeout is scaled
# dynamically in analyze() based on estimated audio duration so that a
# 2-minute answer isn't killed by a 45-second ceiling.
WHISPER_TIMEOUT_SECONDS = float(os.getenv("AUDIO_ANALYSIS_TIMEOUT_SECONDS", "60"))

# webm/opus bitrate estimate used to infer duration from file size.
# ~16 kbps = 2 000 B/s  (matches the fallback estimator so both are consistent).
_BYTES_PER_SECOND_ESTIMATE = 2_000.0

# Safety cap — never wait longer than this regardless of audio length.
_WHISPER_TIMEOUT_MAX_SECONDS = 300.0

# Multiplier: allow N× estimated audio length for Whisper to finish.
# tiny model on CPU transcribes at roughly 2–4× real-time; 4× gives headroom.
_WHISPER_TIMEOUT_MULTIPLIER = 4.0

# beam_size threshold: use greedy decode (beam=1) for long audio to avoid
# multiplicative cost blow-up across Whisper's 30-second internal windows.
_BEAM_SIZE_FAST_THRESHOLD_S = 45.0   # audio ≥ 45 s estimated → greedy

# ── Orchestrator guidance thresholds ──────────────────────────────────────────
# These drive the machine-readable recommendations returned to the intelligence
# engine.  Centralised here so they are tunable in one place.
CONFIDENCE_CRITICAL = 40    # below → strong adaptive action needed
CONFIDENCE_LOW      = 55    # below → mild adaptive action needed
CLARITY_LOW         = 55    # below → communication coaching recommended


# ── Model loader ───────────────────────────────────────────────────────────────

def _get_model():
    global _model_instance
    if _model_instance is None:
        if _ENGINE == "faster_whisper":
            from faster_whisper import WhisperModel
            logger.info("Loading faster-whisper '%s' model (CPU, int8)...", WHISPER_MODEL_NAME)
            _model_instance = WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
        elif _ENGINE == "whisper":
            import whisper as _w
            logger.info("Loading openai-whisper '%s' model...", WHISPER_MODEL_NAME)
            _model_instance = _w.load_model(WHISPER_MODEL_NAME)
    return _model_instance


# ── Helpers ────────────────────────────────────────────────────────────────────

def _wpm_to_rate(wpm: float) -> str:
    if wpm < WPM_SLOW_THRESHOLD:
        return "slow"
    if wpm > WPM_FAST_THRESHOLD:
        return "fast"
    return "medium"


def _detect_fillers(transcript: str) -> Tuple[int, float]:
    """Return (filler_count, filler_ratio). Returns (0, 0.0) for empty/placeholder text."""
    if not transcript or transcript.startswith("["):
        return 0, 0.0
    words = re.findall(r"\b\w+\b", transcript.lower())
    total = len(words)
    if total == 0:
        return 0, 0.0
    count = sum(1 for w in words if w in FILLER_WORDS)

    normalized = " ".join(words)
    for phrase in FILLER_PHRASES:
        count += len(re.findall(rf"\b{re.escape(phrase)}\b", normalized))

    repeated_words = sum(
        1
        for i in range(1, len(words))
        if words[i] == words[i - 1] and words[i] in FILLER_WORDS
    )
    count += repeated_words

    return count, round(count / total, 4)


def _analyze_pauses_fw(seg_list: list, duration_s: float) -> Tuple[int, float, str]:
    """Pause analysis for faster-whisper segments (have .start / .end attrs)."""
    gaps = [
        seg_list[i].start - seg_list[i - 1].end
        for i in range(1, len(seg_list))
    ]
    long_pauses = [g for g in gaps if g > PAUSE_THRESHOLD_S]
    pause_count  = len(long_pauses)
    pause_rate   = pause_count / max(duration_s / 60.0, 0.1)
    return pause_count, pause_rate, _hesitation_level(pause_rate)


def _analyze_pauses_ow(segments: list, duration_s: float) -> Tuple[int, float, str]:
    """Pause analysis for openai-whisper segments (dict with 'start'/'end' keys)."""
    gaps = [
        segments[i]["start"] - segments[i - 1]["end"]
        for i in range(1, len(segments))
    ]
    long_pauses = [g for g in gaps if g > PAUSE_THRESHOLD_S]
    pause_count  = len(long_pauses)
    pause_rate   = pause_count / max(duration_s / 60.0, 0.1)
    return pause_count, pause_rate, _hesitation_level(pause_rate)


def _hesitation_level(pause_rate: float, filler_ratio: float = 0.0, wpm: Optional[float] = None) -> str:
    if pause_rate > PAUSE_RATE_HIGH or filler_ratio >= FILLER_RATIO_HIGH:
        return "high"
    if pause_rate > PAUSE_RATE_MOD or filler_ratio >= FILLER_RATIO_MOD or (wpm is not None and wpm < 70):
        return "moderate"
    return "low"


def _analyze_pitch_stability(audio_path: str) -> str:
    """
    Returns a descriptive pitch label using librosa signal processing.
    No emotion classification — only measures variability.

    "stable"      — natural variation (CV 0.12–0.45)
    "variable"    — high pitch variability (CV > 0.45)
    "monotone"    — very flat delivery (CV < 0.12)
    "unavailable" — librosa not installed or analysis failed
    """
    if not _HAS_LIBROSA:
        return "unavailable"
    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        threshold      = magnitudes.max() * 0.15
        voiced_pitches = pitches[magnitudes > threshold]
        voiced_pitches = voiced_pitches[voiced_pitches > 50]   # ignore sub-bass noise
        if len(voiced_pitches) < 20:
            return "unavailable"
        cv = float(np.std(voiced_pitches)) / max(float(np.mean(voiced_pitches)), 1.0)
        if cv > PITCH_CV_VARIABLE:
            return "variable"
        if cv < PITCH_CV_MONOTONE:
            return "monotone"
        return "stable"
    except Exception as exc:
        logger.debug("Pitch stability analysis failed: %s", exc)
        return "unavailable"


def _check_invalid_audio(
    transcript: str, word_count: int, duration_s: float
) -> Optional[str]:
    """Return a human-readable reason if the audio cannot be reliably analysed."""
    no_speech = (
        not transcript.strip()
        or transcript.strip() in ("[No speech detected]",)
        or transcript.startswith("[No speech")
    )
    if no_speech:
        return "No speech detected in the audio recording."
    if duration_s < MIN_DURATION_SECONDS:
        return "Audio recording is too short for reliable analysis."
    if word_count < MIN_WORDS_FOR_ANALYSIS:
        return "Too few words spoken for reliable communication analysis."
    return None


# ── Scoring ────────────────────────────────────────────────────────────────────

def _score_confidence(
    hesitation_level: str, filler_ratio: float, wpm: float, word_count: int
) -> int:
    """
    Heuristic confidence score.

    Target ranges:
        Weak communication  20–40
        Average             50–70
        Strong              75–90

    Starts at 72 (neutral) and applies deductions for hesitation, fillers,
    and extreme pace.  A longer, well-paced answer earns a small bonus.
    """
    score = 72

    # Hesitation
    if hesitation_level == "high":
        score -= 22
    elif hesitation_level == "moderate":
        score -= 12

    # Filler words
    if filler_ratio > FILLER_RATIO_HIGH:
        score -= 15
    elif filler_ratio > FILLER_RATIO_MOD:
        score -= 7

    # Pace extremes
    if wpm > 210:
        score -= 12
    elif wpm > WPM_FAST_THRESHOLD:
        score -= 5
    elif wpm < 70:
        score -= 10
    elif wpm < WPM_SLOW_THRESHOLD:
        score -= 4

    # Length bonus (adequate response depth)
    if word_count >= 80:
        score += 6
    elif word_count >= 40:
        score += 3

    return max(20, min(90, score))


def _score_clarity(
    speaking_rate: str, word_count: int, filler_ratio: float, hesitation_level: str
) -> int:
    """
    Communication clarity: how structured, complete, and fluent the response is.
    Based on pace, word count, filler frequency, and hesitation level.
    """
    base = {"medium": 76, "slow": 60, "fast": 66}.get(speaking_rate, 68)

    # Response completeness
    if word_count < 15:
        base -= 22
    elif word_count < 40:
        base -= 10
    elif word_count >= 80:
        base += 5

    # Filler disrupts clarity
    if filler_ratio > FILLER_RATIO_HIGH:
        base -= 12
    elif filler_ratio > FILLER_RATIO_MOD:
        base -= 5

    # Hesitation disrupts flow
    if hesitation_level == "high":
        base -= 10
    elif hesitation_level == "moderate":
        base -= 4

    return max(20, min(90, base))


# ── Explainability ─────────────────────────────────────────────────────────────

def _build_notes(
    hesitation_level: str,
    pause_count: int,
    filler_ratio: float,
    filler_count: int,
    speaking_rate: str,
    wpm: float,
    pitch_stability: str,
    word_count: int,
) -> List[str]:
    """Return plain-English observations the frontend can display."""
    notes: List[str] = []

    # Hesitation
    if hesitation_level == "high":
        if pause_count > 0:
            notes.append(f"Frequent hesitation pauses detected ({pause_count} pauses).")
        else:
            notes.append("High hesitation markers detected from repeated filler words.")
    elif hesitation_level == "moderate":
        if pause_count > 0:
            notes.append(f"Some hesitation pauses noted ({pause_count} pauses).")
        else:
            notes.append("Some hesitation markers detected from filler words or slow pacing.")
    else:
        notes.append("Hesitation pauses within an acceptable range.")

    # Filler words
    if filler_ratio > FILLER_RATIO_HIGH:
        notes.append(
            f"High filler-word usage detected "
            f"({filler_count} occurrences, {int(filler_ratio * 100)}% of words)."
        )
    elif filler_ratio > FILLER_RATIO_MOD:
        notes.append(f"Moderate filler-word usage noted ({filler_count} occurrences).")
    else:
        notes.append("Filler-word usage was minimal.")

    # Pace
    if speaking_rate == "fast":
        notes.append(f"Speaking pace was fast ({int(wpm)} wpm) — may indicate nervousness.")
    elif speaking_rate == "slow":
        notes.append(f"Speaking pace was slow ({int(wpm)} wpm) — may indicate uncertainty.")
    else:
        notes.append(f"Speaking pace remained in a natural range ({int(wpm)} wpm).")

    # Pitch
    if pitch_stability == "variable":
        notes.append("High pitch variability observed during the response.")
    elif pitch_stability == "monotone":
        notes.append("Monotone delivery detected — limited pitch variation.")
    elif pitch_stability == "stable":
        notes.append("Vocal pitch remained stable throughout.")
    # "unavailable" → omit pitch note

    # Response depth
    if word_count < 20:
        notes.append("Response was very brief — consider elaborating on your answers.")
    elif word_count >= 80:
        notes.append("Response demonstrated adequate depth and length.")

    return notes


# ── Orchestrator guidance helpers ──────────────────────────────────────────────

def _pace_label(wpm: float, hesitation_level: str, filler_ratio: float) -> str:
    """
    Composite pace label that combines WPM with hesitation and filler signals.
    More informative than the raw speaking_rate bucket alone.

    Labels (ordered by severity):
      slow_with_hesitation  — below 95 WPM + high/moderate hesitation
      slow_with_fillers     — below 95 WPM + moderate fillers
      slow                  — below 95 WPM, otherwise OK
      fast_rambling         — above 210 WPM + fillers or hesitation
      fast_with_fillers     — above 175 WPM + moderate fillers
      fast                  — above 175 WPM, otherwise OK
      measured_with_hesitation — 95-175 WPM + high hesitation
      measured_with_pauses  — 95-175 WPM + moderate hesitation
      good_pace             — 95-175 WPM, hesitation low, fillers low
    """
    if wpm < WPM_SLOW_THRESHOLD:
        if hesitation_level in ("high", "moderate"):
            return "slow_with_hesitation"
        if filler_ratio > FILLER_RATIO_MOD:
            return "slow_with_fillers"
        return "slow"
    if wpm > WPM_FAST_THRESHOLD:
        if wpm > 210 and (hesitation_level != "low" or filler_ratio > FILLER_RATIO_MOD):
            return "fast_rambling"
        if filler_ratio > FILLER_RATIO_MOD:
            return "fast_with_fillers"
        return "fast"
    # 95–175 WPM range — inspect hesitation
    if hesitation_level == "high":
        return "measured_with_hesitation"
    if hesitation_level == "moderate":
        return "measured_with_pauses"
    return "good_pace"


def _detect_audio_issue(
    hesitation_level: str,
    filler_ratio: float,
    wpm: float,
    word_count: int,
    pitch_stability: str,
    pause_count: int,
) -> Optional[str]:
    """
    Identify the single most prominent communication issue.
    Returns a plain-English string or None when no notable issue found.
    Priority order: brevity → hesitation → fillers → pace → pitch.
    """
    if word_count < 20:
        return "Very brief response — insufficient detail for reliable assessment"
    if hesitation_level == "high" and pause_count >= 3:
        return f"High hesitation with {pause_count} long pauses detected"
    if hesitation_level == "high":
        return "High hesitation markers detected (frequent filler words or repeated restarts)"
    if filler_ratio > FILLER_RATIO_HIGH:
        return f"Excessive filler words ({round(filler_ratio * 100)}% of speech)"
    if hesitation_level == "moderate" and pause_count >= 2:
        return f"Moderate hesitation — {pause_count} pauses and some filler words"
    if wpm < 70:
        return f"Very slow pace ({int(wpm)} WPM) suggesting uncertainty or difficulty recalling"
    if wpm > 210:
        return f"Very fast pace ({int(wpm)} WPM) suggesting nervousness or rushing"
    if filler_ratio > FILLER_RATIO_MOD:
        return f"Moderate filler word usage ({round(filler_ratio * 100)}% of speech)"
    if pitch_stability == "monotone":
        return "Monotone delivery — limited vocal engagement across the response"
    return None  # no prominent issue


def _orchestrator_recommendation(
    confidence: int,
    clarity: int,
    hesitation_level: str,
    word_count: int,
) -> str:
    """
    Machine-readable hint for the intelligence engine.

    The intelligence engine uses this alongside the technical score to decide:
    - whether to decrease difficulty
    - whether to add an encouragement note to the next question
    - whether to ask for a structured re-explanation
    """
    if confidence < CONFIDENCE_CRITICAL and clarity < CLARITY_LOW:
        return "give_encouragement_and_ask_simpler_question"
    if confidence < CONFIDENCE_LOW and hesitation_level == "high":
        return "reduce_difficulty_and_add_encouragement"
    if confidence < CONFIDENCE_LOW:
        return "monitor_confidence_maintain_difficulty"
    if clarity < CLARITY_LOW and word_count < 30:
        return "ask_for_structured_elaboration"
    if clarity < CLARITY_LOW:
        return "request_clearer_explanation"
    if confidence >= 75 and clarity >= 75:
        return "increase_difficulty"
    return "continue_standard_flow"


def _coaching_tip(
    hesitation_level: str,
    filler_ratio: float,
    wpm: float,
    clarity: int,
    word_count: int,
) -> Optional[str]:
    """
    Return the single highest-impact coaching tip for the candidate.
    Priority matches _detect_audio_issue to be consistent.
    """
    if word_count < 20:
        return (
            "Structure your answer: define the concept, give a real example, "
            "then discuss the main trade-off."
        )
    if hesitation_level == "high" and filler_ratio > FILLER_RATIO_MOD:
        return (
            "Replace 'um' and 'uh' with a 1-second silence — "
            "it sounds more confident and gives you thinking time."
        )
    if hesitation_level == "high":
        return (
            "Try the pause-before-answer technique: take 3 seconds of silence "
            "to collect your thoughts before responding."
        )
    if filler_ratio > FILLER_RATIO_HIGH:
        return (
            "Practice speaking in short, structured sentences: "
            "Problem → Approach → Trade-off → Result."
        )
    if wpm > 200:
        return (
            "Slow down and emphasise key technical terms — "
            "interviewers need processing time for complex concepts."
        )
    if wpm < 80:
        return (
            "Increase your pace slightly — aim for 110-140 WPM "
            "for confident, natural technical delivery."
        )
    if clarity < CLARITY_LOW:
        return (
            "Use the STAR method: Situation → Task → Action → Result "
            "to give structured, memorable answers."
        )
    return None


def _audio_reasoning_summary(
    wpm: float,
    hesitation_level: str,
    filler_ratio: float,
    confidence: int,
    clarity: int,
    pause_count: int,
    word_count: int,
) -> str:
    """
    Plain-English narrative summarising the audio analysis for the UI and
    final feedback report.  Written to be read by the candidate, not a developer.
    """
    # Response length description
    if word_count < 20:
        length_desc = "very brief"
    elif word_count >= 80:
        length_desc = f"well-developed ({word_count} words)"
    else:
        length_desc = f"moderate length ({word_count} words)"

    # Pace description
    if wpm < 80:
        pace_desc = f"slow pace ({int(wpm)} WPM)"
    elif wpm > 200:
        pace_desc = f"fast pace ({int(wpm)} WPM) suggesting some nervousness"
    else:
        pace_desc = f"natural pace ({int(wpm)} WPM)"

    # Hesitation
    if hesitation_level == "high":
        hesit_desc = f"{pause_count} notable pauses with high hesitation markers"
    elif hesitation_level == "moderate":
        hesit_desc = f"some hesitation ({pause_count} pauses)"
    else:
        hesit_desc = "minimal hesitation"

    # Fillers
    if filler_ratio > FILLER_RATIO_HIGH:
        filler_desc = f" and excessive filler words ({round(filler_ratio * 100)}% of speech)"
    elif filler_ratio > FILLER_RATIO_MOD:
        filler_desc = f" and some filler words ({round(filler_ratio * 100)}% of speech)"
    else:
        filler_desc = ""

    summary = (
        f"Response was {length_desc}, delivered at a {pace_desc}, "
        f"with {hesit_desc}{filler_desc}."
    )

    # Overall score interpretation
    if confidence >= 70 and clarity >= 70:
        summary += " Overall delivery was confident and clear."
    elif confidence < CONFIDENCE_CRITICAL and clarity < CLARITY_LOW:
        summary += (
            " Both confidence and communication clarity were below expectations — "
            "targeted practice will help significantly."
        )
    elif confidence < CONFIDENCE_LOW:
        summary += (
            " Confidence indicators were below target — "
            "consider pacing, pause reduction, and filler awareness."
        )
    elif clarity < CLARITY_LOW:
        summary += (
            " Communication structure could be improved with "
            "clearer examples and a more structured answer format."
        )

    return summary


def _invalid_audio_result(transcript: str, duration_s: float, word_count: int, wpm: float, mode: str) -> dict:
    return {
        "status":                        "invalid_audio",
        "reason":                        "Insufficient audio quality for reliable communication analysis.",
        "transcript":                    transcript,
        "confidence_score":              0,
        "communication_clarity_score":   0,
        "pause_count":                   0,
        "speaking_rate":                 _wpm_to_rate(wpm),
        "words_per_minute":              round(wpm, 1),
        "filler_word_count":             0,
        "filler_ratio":                  0.0,
        "hesitation_level":              "low",
        "pitch_stability":               "unavailable",
        "analysis_notes":                ["Audio quality too low for reliable communication analysis."],
        "mode":                          mode,
        "word_count":                    word_count,
        "duration_seconds":              round(duration_s, 1),
        "hesitation_count":              0,
        "hesitation_rate":               0.0,
        "pause_rate_per_minute":         0.0,
        "pitch_variation_proxy":         None,
        "volume_energy_proxy":           None,
        "tone_proxy":                    "insufficient_audio",
        "metrics_source":                mode if mode in ("faster_whisper", "whisper") else "heuristic",
        # Orchestrator guidance — None for invalid audio
        "pace_label":                    None,
        "detected_issue":                "Very brief response — insufficient detail for reliable assessment",
        "recommendation_to_orchestrator": "give_encouragement_and_ask_simpler_question",
        "coaching_tip":                  (
            "Structure your answer: define the concept, give a real example, "
            "then discuss the main trade-off."
        ),
        "audio_reasoning_summary":       (
            "Audio could not be reliably analysed — the recording was too short "
            "or contained no detectable speech."
        ),
    }


# ── Whisper analysers ──────────────────────────────────────────────────────────

def _analyze_faster_whisper(audio_path: str) -> dict:
    model = _get_model()

    # Estimate audio duration from file size so we can pick an efficient
    # beam_size before spending CPU cycles transcribing.
    import os as _os_local
    file_size_bytes = _os_local.path.getsize(audio_path)
    est_duration_s  = max(2.0, file_size_bytes / _BYTES_PER_SECOND_ESTIMATE)

    # For longer audio each Whisper 30-second window is processed separately;
    # beam_size=5 multiplies cost by 5 per window.  Greedy (beam=1) is ~3-5×
    # faster with minimal accuracy loss on clear interview speech.
    beam_size = 1 if est_duration_s >= _BEAM_SIZE_FAST_THRESHOLD_S else 5

    logger.debug(
        "faster_whisper: file=%d B, est=%.1fs, beam_size=%d",
        file_size_bytes, est_duration_s, beam_size,
    )

    segments, info = model.transcribe(
        audio_path,
        beam_size=beam_size,
        word_timestamps=False,
        condition_on_previous_text=True,  # maintain context across 30-s windows
    )
    seg_list = list(segments)

    transcript   = " ".join(s.text.strip() for s in seg_list).strip() or "[No speech detected]"
    duration_s   = max(info.duration, 0.01)
    word_count   = len(transcript.split()) if not transcript.startswith("[") else 0

    wpm          = (word_count / duration_s) * 60
    speaking_rate = _wpm_to_rate(wpm)

    invalid_reason = _check_invalid_audio(transcript, word_count, duration_s)
    if invalid_reason:
        return _invalid_audio_result(transcript, duration_s, word_count, wpm, "faster_whisper")

    pause_count, pause_rate, hesitation_level = _analyze_pauses_fw(seg_list, duration_s)
    filler_count, filler_ratio                = _detect_fillers(transcript)
    hesitation_level                          = _hesitation_level(pause_rate, filler_ratio, wpm)
    pitch_stability                           = _analyze_pitch_stability(audio_path)

    confidence = _score_confidence(hesitation_level, filler_ratio, wpm, word_count)
    clarity    = _score_clarity(speaking_rate, word_count, filler_ratio, hesitation_level)
    notes      = _build_notes(
        hesitation_level, pause_count, filler_ratio, filler_count,
        speaking_rate, wpm, pitch_stability, word_count,
    )

    return {
        "status":                        "ok",
        "transcript":                    transcript,
        "confidence_score":              confidence,
        "communication_clarity_score":   clarity,
        "pause_count":                   pause_count,
        "speaking_rate":                 speaking_rate,
        "words_per_minute":              round(wpm, 1),
        "filler_word_count":             filler_count,
        "filler_ratio":                  round(filler_ratio, 4),
        "hesitation_level":              hesitation_level,
        "pitch_stability":               pitch_stability,
        "analysis_notes":                notes,
        "mode":                          "faster_whisper",
        "word_count":                    word_count,
        "duration_seconds":              round(duration_s, 1),
        "hesitation_count":              pause_count,
        "hesitation_rate":               round(pause_rate, 2),
        "pause_rate_per_minute":         round(pause_rate, 2),
        "pitch_variation_proxy":         None,
        "volume_energy_proxy":           None,
        "tone_proxy":                    "measured_speech_proxy",
        "metrics_source":                "whisper",
        "reason":                        None,
        # Orchestrator guidance
        "pace_label":                    _pace_label(wpm, hesitation_level, filler_ratio),
        "detected_issue":                _detect_audio_issue(
                                             hesitation_level, filler_ratio, wpm,
                                             word_count, pitch_stability, pause_count
                                         ),
        "recommendation_to_orchestrator": _orchestrator_recommendation(
                                             confidence, clarity, hesitation_level, word_count
                                         ),
        "coaching_tip":                  _coaching_tip(
                                             hesitation_level, filler_ratio, wpm, clarity, word_count
                                         ),
        "audio_reasoning_summary":       _audio_reasoning_summary(
                                             wpm, hesitation_level, filler_ratio,
                                             confidence, clarity, pause_count, word_count
                                         ),
    }


def _analyze_openai_whisper(audio_path: str) -> dict:
    model      = _get_model()
    result     = model.transcribe(audio_path)
    transcript = result.get("text", "").strip() or "[No speech detected]"
    segments   = result.get("segments", [])
    duration_s = max(result.get("duration", 1.0), 0.01)
    word_count = len(transcript.split()) if not transcript.startswith("[") else 0

    wpm          = (word_count / duration_s) * 60
    speaking_rate = _wpm_to_rate(wpm)

    invalid_reason = _check_invalid_audio(transcript, word_count, duration_s)
    if invalid_reason:
        return _invalid_audio_result(transcript, duration_s, word_count, wpm, "whisper")

    pause_count, pause_rate, hesitation_level = _analyze_pauses_ow(segments, duration_s)
    filler_count, filler_ratio                = _detect_fillers(transcript)
    hesitation_level                          = _hesitation_level(pause_rate, filler_ratio, wpm)
    pitch_stability                           = _analyze_pitch_stability(audio_path)

    confidence = _score_confidence(hesitation_level, filler_ratio, wpm, word_count)
    clarity    = _score_clarity(speaking_rate, word_count, filler_ratio, hesitation_level)
    notes      = _build_notes(
        hesitation_level, pause_count, filler_ratio, filler_count,
        speaking_rate, wpm, pitch_stability, word_count,
    )

    return {
        "status":                        "ok",
        "transcript":                    transcript,
        "confidence_score":              confidence,
        "communication_clarity_score":   clarity,
        "pause_count":                   pause_count,
        "speaking_rate":                 speaking_rate,
        "words_per_minute":              round(wpm, 1),
        "filler_word_count":             filler_count,
        "filler_ratio":                  round(filler_ratio, 4),
        "hesitation_level":              hesitation_level,
        "pitch_stability":               pitch_stability,
        "analysis_notes":                notes,
        "mode":                          "whisper",
        "word_count":                    word_count,
        "duration_seconds":              round(duration_s, 1),
        "hesitation_count":              pause_count,
        "hesitation_rate":               round(pause_rate, 2),
        "pause_rate_per_minute":         round(pause_rate, 2),
        "pitch_variation_proxy":         None,
        "volume_energy_proxy":           None,
        "tone_proxy":                    "measured_speech_proxy",
        "metrics_source":                "whisper",
        "reason":                        None,
        # Orchestrator guidance
        "pace_label":                    _pace_label(wpm, hesitation_level, filler_ratio),
        "detected_issue":                _detect_audio_issue(
                                             hesitation_level, filler_ratio, wpm,
                                             word_count, pitch_stability, pause_count
                                         ),
        "recommendation_to_orchestrator": _orchestrator_recommendation(
                                             confidence, clarity, hesitation_level, word_count
                                         ),
        "coaching_tip":                  _coaching_tip(
                                             hesitation_level, filler_ratio, wpm, clarity, word_count
                                         ),
        "audio_reasoning_summary":       _audio_reasoning_summary(
                                             wpm, hesitation_level, filler_ratio,
                                             confidence, clarity, pause_count, word_count
                                         ),
    }


# ── Fallback analyser ──────────────────────────────────────────────────────────

def _analyze_fallback(file_bytes: bytes) -> dict:
    """
    Conservative heuristic scores when no Whisper engine is installed.
    Uses file size as a duration proxy.  RNG is seeded from file size so the
    same recording always produces the same scores (reproducible for demos).

    Scores are capped at 60 to signal that this is a limited-mode estimate.
    """
    file_size  = len(file_bytes)
    duration_s = max(2.0, file_size / 2_000.0)   # webm/opus ≈ 16 kbps ≈ 2 000 B/s
    rng        = random.Random(file_size % 99_991)

    if duration_s < 5:
        speaking_rate, wpm_est = "fast",   160
    elif duration_s < 90:
        speaking_rate, wpm_est = "medium", 125
    else:
        speaking_rate, wpm_est = "slow",   90

    word_count_est = max(5, int(duration_s * wpm_est / 60))
    pause_count    = max(0, int(duration_s / 15) + rng.randint(-1, 2))
    pause_rate     = pause_count / max(duration_s / 60.0, 0.1)
    hesitation_level = _hesitation_level(pause_rate)

    # Conservative: max 55 so these cannot be mistaken for real scores
    confidence = max(20, min(55, 40 + rng.randint(-8, 8)))
    clarity    = max(20, min(55, 40 + rng.randint(-8, 8)))

    transcript = (
        f"[Audio recorded — approximately {int(duration_s)}s, "
        f"~{word_count_est} words estimated. "
        "Install faster-whisper for real transcription: pip install faster-whisper]"
    )

    notes = [
        "Analysis performed in fallback mode — Whisper transcription not available.",
        "Scores are conservative estimates based on audio duration only.",
        "Install faster-whisper for accurate communication analysis.",
    ]

    return {
        "status":                        "ok",
        "transcript":                    transcript,
        "confidence_score":              confidence,
        "communication_clarity_score":   clarity,
        "pause_count":                   pause_count,
        "speaking_rate":                 speaking_rate,
        "words_per_minute":              round(float(wpm_est), 1),
        "filler_word_count":             0,
        "filler_ratio":                  0.0,
        "hesitation_level":              hesitation_level,
        "pitch_stability":               "unavailable",
        "analysis_notes":                notes,
        "mode":                          "fallback",
        "word_count":                    word_count_est,
        "duration_seconds":              round(duration_s, 1),
        "hesitation_count":              pause_count,
        "hesitation_rate":               round(pause_rate, 2),
        "pause_rate_per_minute":         round(pause_rate, 2),
        "pitch_variation_proxy":         None,
        "volume_energy_proxy":           None,
        "tone_proxy":                    "heuristic_unknown",
        "metrics_source":                "heuristic",
        "reason":                        None,
        # Orchestrator guidance — conservative values in fallback mode
        "pace_label":                    _pace_label(float(wpm_est), hesitation_level, 0.0),
        "detected_issue":                None,   # can't detect real issues without transcript
        "recommendation_to_orchestrator": "continue_standard_flow",
        "coaching_tip":                  None,
        "audio_reasoning_summary":       (
            f"Analysis performed in fallback mode — Whisper transcription not available. "
            f"Estimated duration: {int(duration_s)}s at approximately {wpm_est} WPM. "
            "Scores are conservative heuristic estimates only."
        ),
    }


# ── Public entry point ─────────────────────────────────────────────────────────

async def analyze(file_bytes: bytes, filename: str = "audio.webm") -> dict:
    """
    Accepts raw audio bytes, writes to a temp file, analyses, cleans up.
    Always returns a dict matching AudioAnalysisResponse fields.
    Falls back gracefully if the Whisper engine fails at runtime.

    Whisper inference is CPU-bound and synchronous.  We offload it to the
    default ThreadPoolExecutor so the FastAPI event loop is never blocked,
    which allows audio + video to run concurrently via asyncio.gather().

    Timeout is DYNAMIC: we estimate audio duration from file size and allow
    up to _WHISPER_TIMEOUT_MULTIPLIER × that estimate, floored at
    WHISPER_TIMEOUT_SECONDS and capped at _WHISPER_TIMEOUT_MAX_SECONDS.
    This prevents a fixed 45-second ceiling from killing 60-120 second answers
    where Whisper (tiny, CPU, beam_size=5) legitimately needs more time.
    """
    if _ENGINE == "fallback":
        return _analyze_fallback(file_bytes)

    # ── Dynamic timeout ───────────────────────────────────────────────────────
    # Estimate duration before writing to disk (avoids extra stat call).
    estimated_duration_s = max(2.0, len(file_bytes) / _BYTES_PER_SECOND_ESTIMATE)
    timeout = min(
        _WHISPER_TIMEOUT_MAX_SECONDS,
        max(WHISPER_TIMEOUT_SECONDS, estimated_duration_s * _WHISPER_TIMEOUT_MULTIPLIER),
    )
    logger.info(
        "audio analyze: %d B, est_duration=%.1fs, whisper_timeout=%.0fs",
        len(file_bytes), estimated_duration_s, timeout,
    )

    suffix = Path(filename).suffix or ".webm"
    tmp    = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(file_bytes)
        tmp.flush()
        tmp.close()

        if _ENGINE == "faster_whisper":
            return await asyncio.wait_for(
                asyncio.to_thread(_analyze_faster_whisper, tmp.name),
                timeout=timeout,
            )
        return await asyncio.wait_for(
            asyncio.to_thread(_analyze_openai_whisper, tmp.name),
            timeout=timeout,
        )

    except asyncio.TimeoutError:
        logger.warning(
            "Whisper analysis timed out after %.0fs (est_duration=%.1fs) — "
            "falling back to heuristics.",
            timeout, estimated_duration_s,
        )
        result = _analyze_fallback(file_bytes)
        result["analysis_notes"].insert(
            0,
            f"Whisper transcription timed out after {int(timeout)}s "
            f"(estimated audio: {int(estimated_duration_s)}s); "
            "heuristic scoring used for this turn.",
        )
        result["reason"] = "Whisper transcription timed out."
        return result
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
