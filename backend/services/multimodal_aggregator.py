"""Weighted multimodal scoring used by adaptation and final feedback.

TASK 4: Role-aware weight tables.
TASK 5: Multimodal signal classification for orchestrator decisions.

Backward compatibility:
  - aggregate_turn() still returns a "weights" key — existing tests check
    result["weights"]["technical"] == 0.45.  When no role is supplied the
    default weights (technical=0.45) are used, so the check still passes.
  - The new keys "weights_used", "reason", "multimodal_signal" are additive.
"""

from statistics import mean
from typing import Any

# ── Default weights (no role supplied) ───────────────────────────────────────

_DEFAULT_WEIGHTS: dict[str, float] = {
    "technical":     0.45,
    "communication": 0.20,
    "confidence":    0.15,
    "engagement":    0.10,
    "role_fit":      0.10,
}

# ── Role-aware weight tables ──────────────────────────────────────────────────
# Keys are lower-cased canonical role names (matched via lower().strip()).
# Each row must sum to 1.0.

_ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    "backend developer": {
        "technical": 0.55, "communication": 0.15,
        "confidence": 0.10, "engagement": 0.10, "role_fit": 0.10,
    },
    "frontend developer": {
        "technical": 0.50, "communication": 0.20,
        "confidence": 0.10, "engagement": 0.10, "role_fit": 0.10,
    },
    "full stack developer": {
        "technical": 0.50, "communication": 0.18,
        "confidence": 0.12, "engagement": 0.10, "role_fit": 0.10,
    },
    "software engineer": {
        "technical": 0.50, "communication": 0.20,
        "confidence": 0.12, "engagement": 0.08, "role_fit": 0.10,
    },
    "product manager": {
        "technical": 0.20, "communication": 0.35,
        "confidence": 0.20, "engagement": 0.15, "role_fit": 0.10,
    },
    "data scientist": {
        "technical": 0.50, "communication": 0.20,
        "confidence": 0.12, "engagement": 0.08, "role_fit": 0.10,
    },
    "machine learning engineer": {
        "technical": 0.52, "communication": 0.18,
        "confidence": 0.10, "engagement": 0.10, "role_fit": 0.10,
    },
    "devops engineer": {
        "technical": 0.52, "communication": 0.18,
        "confidence": 0.10, "engagement": 0.10, "role_fit": 0.10,
    },
    "data engineer": {
        "technical": 0.52, "communication": 0.18,
        "confidence": 0.10, "engagement": 0.10, "role_fit": 0.10,
    },
    "qa engineer": {
        "technical": 0.45, "communication": 0.22,
        "confidence": 0.13, "engagement": 0.10, "role_fit": 0.10,
    },
}

# Keep the old name as an alias so any external code that imported WEIGHTS
# directly still works without modification.
WEIGHTS = _DEFAULT_WEIGHTS


# ── Role helpers ──────────────────────────────────────────────────────────────

def _get_weights(role: str) -> tuple[dict[str, float], str]:
    """
    Return (weight_dict, reason_string) for the given role.
    Falls back to _DEFAULT_WEIGHTS when the role is unknown or empty.
    """
    normalised = role.strip().lower()
    if normalised in _ROLE_WEIGHTS:
        return _ROLE_WEIGHTS[normalised], f"role_aware:{normalised.replace(' ', '_')}"
    return _DEFAULT_WEIGHTS, "default_weights"


# ── Signal classifier (TASK 5) ────────────────────────────────────────────────

def _classify_signal(
    technical: int,
    confidence: int,
    communication: int,
    engagement: int,
) -> str:
    """
    Return a machine-readable signal label for the intelligence engine.

    Labels (in priority order):
      strong_technical_low_confidence   — knows the material but seems nervous
      weak_technical_low_confidence     — struggling technically AND behaviourally
      weak_technical_needs_coaching     — weak tech + low confidence (no comm issue)
      strong_candidate                  — high tech + good confidence + good comm
      confidence_and_engagement_low     — behavioural signals dominate
      communication_needs_improvement   — communication below threshold
      confidence_low                    — confidence below threshold only
      strong_technical                  — solid technical, behavioural OK
      average_performance               — nothing notably high or low
    """
    strong_tech = technical    >= 70
    low_conf    = confidence   < 55
    weak_tech   = technical    < 50
    low_comm    = communication < 50
    low_eng     = engagement   < 45

    if strong_tech and low_conf:
        return "strong_technical_low_confidence"
    if weak_tech and low_conf and low_comm:
        return "weak_technical_low_confidence"
    if weak_tech and low_conf:
        return "weak_technical_needs_coaching"
    if strong_tech and not low_conf and communication >= 65:
        return "strong_candidate"
    if low_conf and low_eng:
        return "confidence_and_engagement_low"
    if low_comm:
        return "communication_needs_improvement"
    if low_conf:
        return "confidence_low"
    if strong_tech:
        return "strong_technical"
    return "average_performance"


# ── Utilities ─────────────────────────────────────────────────────────────────

def _avg(values: list[int], default: int) -> int:
    clean = [int(v) for v in values if v is not None]
    return round(mean(clean)) if clean else default


def latest_for_question(items: list[dict], question_number: int | None) -> dict | None:
    if question_number is None:
        return items[-1] if items else None
    matches = [i for i in items if i.get("question_number") == question_number]
    return matches[-1] if matches else None


# ── Turn aggregator ───────────────────────────────────────────────────────────

def aggregate_turn(
    evaluation: dict,
    audio_score: dict | None = None,
    video_score: dict | None = None,
    role_fit_score: int = 70,
    *,
    role: str = "",
) -> dict[str, Any]:
    """
    Aggregate per-turn multimodal scores into a single combined score.

    Parameters
    ----------
    evaluation      : dict from the technical evaluator (technical_score, depth_score …)
    audio_score     : dict from audio_analyzer.analyze() — may be None
    video_score     : dict from video_analyzer.analyze() — may be None
    role_fit_score  : 0-100 pre-computed role fit
    role            : candidate's target role (e.g. "Backend Developer").
                      Drives weight selection.  Keyword-only to maintain
                      backward compatibility with positional callers.

    Returns
    -------
    dict with keys:
      technical_score, communication_score, confidence_score, engagement_score,
      role_fit_score, combined_score,
      weights          — selected weight dict (kept for backward compat)
      weights_used     — alias for weights (NEW)
      reason           — weight-selection reason string (NEW)
      multimodal_signal — machine-readable signal label (NEW)
      evidence         — list of plain-English evidence bullets
      source           — "multimodal" | "audio" | "video" | "typed_proxy"
    """
    weights, reason = _get_weights(role)

    technical     = int(evaluation.get("technical_score", 0))
    depth         = int(evaluation.get("depth_score", 0))
    communication = (int(audio_score.get("communication_clarity_score", 60))
                     if audio_score else max(35, min(80, depth)))
    confidence    = (int(audio_score.get("confidence_score", 60))
                     if audio_score else max(30, min(78, round((technical + depth) / 2))))
    engagement    = (int(video_score.get("engagement_score", 65))
                     if video_score else 62)

    evidence: list[str] = [
        f"Technical score: {technical}/100",
        f"Communication clarity: {communication}/100"
        + (" from audio" if audio_score else " typed-answer proxy"),
        f"Confidence: {confidence}/100"
        + (" from audio" if audio_score else " technical/depth proxy"),
        f"Engagement: {engagement}/100"
        + (" from video" if video_score else " default proxy"),
    ]

    if audio_score:
        pauses     = audio_score.get("pause_count", 0)
        hesitation = audio_score.get("hesitation_count", 0)
        if pauses or hesitation:
            penalty    = min(12, int(pauses) * 2 + int(hesitation))
            confidence = max(0, confidence - penalty)
            evidence.append(
                f"Confidence adjusted for {pauses} pause(s) and {hesitation} hesitation marker(s)"
            )

        # Surface audio orchestrator recommendation in evidence when notable
        audio_rec = audio_score.get("recommendation_to_orchestrator", "")
        if audio_rec and audio_rec not in ("continue_standard_flow", "increase_difficulty"):
            evidence.append(f"Audio signal: {audio_rec.replace('_', ' ')}")

    stress = (
        (video_score or {}).get("stress_indicator")
        or (video_score or {}).get("stress_nervousness_indicator")
        or (video_score or {}).get("movement_activity")
    )
    stress_norm = str(stress or "").lower()
    if stress_norm in {"high", "elevated", "unstable"}:
        confidence = max(0, confidence - 8)
        engagement = max(0, engagement - 5)
        evidence.append("Elevated visual stress proxy reduced confidence/engagement")
    elif stress_norm in {"medium", "moderate"}:
        confidence = max(0, confidence - 3)
        evidence.append("Moderate visual stress proxy noted")

    # Surface video orchestrator recommendation when notable
    if video_score:
        video_rec = video_score.get("recommendation_to_orchestrator", "")
        if video_rec and video_rec not in ("no_video_action_needed",):
            evidence.append(f"Video signal: {video_rec.replace('_', ' ')}")

    combined = round(
        technical     * weights["technical"]
        + communication * weights["communication"]
        + confidence    * weights["confidence"]
        + engagement    * weights["engagement"]
        + role_fit_score * weights["role_fit"]
    )

    multimodal_signal = _classify_signal(technical, confidence, communication, engagement)

    source = (
        "multimodal" if audio_score and video_score
        else "audio"  if audio_score
        else "video"  if video_score
        else "typed_proxy"
    )

    return {
        "technical_score":    technical,
        "communication_score": communication,
        "confidence_score":   confidence,
        "engagement_score":   engagement,
        "role_fit_score":     role_fit_score,
        "combined_score":     combined,
        "weights":            weights,       # backward compat — do not rename
        "weights_used":       weights,       # explicit alias for new consumers
        "reason":             reason,
        "multimodal_signal":  multimodal_signal,
        "evidence":           evidence,
        "source":             source,
    }


# ── Session aggregator ────────────────────────────────────────────────────────

def aggregate_session(
    answers: list[dict],
    audio_scores: list[dict],
    video_scores: list[dict],
    role_fit_score: int,
    *,
    role: str = "",
) -> dict[str, Any]:
    if not answers:
        return aggregate_turn({}, None, None, role_fit_score, role=role)

    turns = []
    for idx, answer in enumerate(answers, start=1):
        turns.append(aggregate_turn(
            answer.get("evaluation", {}),
            latest_for_question(audio_scores, idx),
            latest_for_question(video_scores, idx),
            role_fit_score,
            role=role,
        ))

    weights, reason = _get_weights(role)

    # Dominant signal across the session (most frequent)
    signals = [t["multimodal_signal"] for t in turns]
    dominant_signal = max(set(signals), key=signals.count) if signals else "average_performance"

    return {
        "technical_score":    _avg([t["technical_score"]    for t in turns], 0),
        "communication_score": _avg([t["communication_score"] for t in turns], 60),
        "confidence_score":   _avg([t["confidence_score"]   for t in turns], 60),
        "engagement_score":   _avg([t["engagement_score"]   for t in turns], 62),
        "role_fit_score":     role_fit_score,
        "combined_score":     _avg([t["combined_score"]     for t in turns], 0),
        "weights":            weights,
        "weights_used":       weights,
        "reason":             reason,
        "multimodal_signal":  dominant_signal,
        "evidence":           [e for t in turns for e in t["evidence"][:2]][:8],
        "turns":              turns,
        "source": (
            "multimodal" if audio_scores and video_scores
            else "audio"  if audio_scores
            else "video"  if video_scores
            else "typed_proxy"
        ),
    }
