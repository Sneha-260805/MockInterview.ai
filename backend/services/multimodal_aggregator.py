"""Weighted multimodal scoring used by adaptation and final feedback."""

from statistics import mean
from typing import Any

WEIGHTS = {
    "technical": 0.45,
    "communication": 0.20,
    "confidence": 0.15,
    "engagement": 0.10,
    "role_fit": 0.10,
}


def _avg(values: list[int], default: int) -> int:
    clean = [int(v) for v in values if v is not None]
    return round(mean(clean)) if clean else default


def latest_for_question(items: list[dict], question_number: int | None) -> dict | None:
    if question_number is None:
        return items[-1] if items else None
    matches = [i for i in items if i.get("question_number") == question_number]
    return matches[-1] if matches else None


def aggregate_turn(
    evaluation: dict,
    audio_score: dict | None = None,
    video_score: dict | None = None,
    role_fit_score: int = 70,
) -> dict[str, Any]:
    technical = int(evaluation.get("technical_score", 0))
    depth = int(evaluation.get("depth_score", 0))
    communication = int(audio_score.get("communication_clarity_score", 60)) if audio_score else max(35, min(80, depth))
    confidence = int(audio_score.get("confidence_score", 60)) if audio_score else max(30, min(78, round((technical + depth) / 2)))
    engagement = int(video_score.get("engagement_score", 65)) if video_score else 62

    evidence: list[str] = [
        f"Technical score: {technical}/100",
        f"Communication clarity: {communication}/100" + (" from audio" if audio_score else " typed-answer proxy"),
        f"Confidence: {confidence}/100" + (" from audio" if audio_score else " technical/depth proxy"),
        f"Engagement: {engagement}/100" + (" from video" if video_score else " default proxy"),
    ]

    if audio_score:
        pauses = audio_score.get("pause_count", 0)
        hesitation = audio_score.get("hesitation_count", 0)
        if pauses or hesitation:
            penalty = min(12, int(pauses) * 2 + int(hesitation))
            confidence = max(0, confidence - penalty)
            evidence.append(f"Confidence adjusted for {pauses} pause(s) and {hesitation} hesitation marker(s)")

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

    combined = round(
        technical * WEIGHTS["technical"]
        + communication * WEIGHTS["communication"]
        + confidence * WEIGHTS["confidence"]
        + engagement * WEIGHTS["engagement"]
        + role_fit_score * WEIGHTS["role_fit"]
    )

    return {
        "technical_score": technical,
        "communication_score": communication,
        "confidence_score": confidence,
        "engagement_score": engagement,
        "role_fit_score": role_fit_score,
        "combined_score": combined,
        "weights": WEIGHTS,
        "evidence": evidence,
        "source": "multimodal" if audio_score and video_score else "audio" if audio_score else "video" if video_score else "typed_proxy",
    }


def aggregate_session(
    answers: list[dict],
    audio_scores: list[dict],
    video_scores: list[dict],
    role_fit_score: int,
) -> dict[str, Any]:
    if not answers:
        return aggregate_turn({}, None, None, role_fit_score)
    turns = []
    for idx, answer in enumerate(answers, start=1):
        turns.append(aggregate_turn(
            answer.get("evaluation", {}),
            latest_for_question(audio_scores, idx),
            latest_for_question(video_scores, idx),
            role_fit_score,
        ))
    return {
        "technical_score": _avg([t["technical_score"] for t in turns], 0),
        "communication_score": _avg([t["communication_score"] for t in turns], 60),
        "confidence_score": _avg([t["confidence_score"] for t in turns], 60),
        "engagement_score": _avg([t["engagement_score"] for t in turns], 62),
        "role_fit_score": role_fit_score,
        "combined_score": _avg([t["combined_score"] for t in turns], 0),
        "weights": WEIGHTS,
        "evidence": [e for t in turns for e in t["evidence"][:2]][:8],
        "turns": turns,
        "source": "multimodal" if audio_scores and video_scores else "audio" if audio_scores else "video" if video_scores else "typed_proxy",
    }
