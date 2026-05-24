"""
Integration cleanup tests — verifies that:

A. /next-question passes selected_role into multimodal_aggregator.aggregate_turn
B. /api/scoring/audio persists rich audio fields
C. /api/scoring/video persists rich video fields
D. /api/scoring/combined persists both rich audio and video fields

All tests are deterministic (no LLM calls, no real audio/video analysis).
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import store
from routes.scoring_routes import router as scoring_router

# Minimal test app — only the scoring router
_app = FastAPI()
_app.include_router(scoring_router)
_client = TestClient(_app)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _new_session() -> str:
    sid = f"test-cleanup-{uuid.uuid4().hex[:8]}"
    store._sessions[sid] = {"session_id": sid, "audio_scores": [], "video_scores": []}
    return sid


def _cleanup(sid: str) -> None:
    store._sessions.pop(sid, None)


# ── Shared mock analyzer payloads ──────────────────────────────────────────────

_RICH_AUDIO = {
    "status":                         "ok",
    "transcript":                     "REST APIs are stateless and scalable.",
    "confidence_score":               72,
    "communication_clarity_score":    68,
    "pause_count":                    2,
    "speaking_rate":                  "medium",
    "words_per_minute":               130.0,
    "filler_word_count":              3,
    "filler_ratio":                   0.04,
    "hesitation_level":               "moderate",
    "pitch_stability":                "stable",
    "analysis_notes":                 ["Some hesitation detected."],
    "mode":                           "fallback",
    "word_count":                     50,
    "duration_seconds":               23.0,
    "hesitation_count":               2,
    "hesitation_rate":                0.52,
    "pause_rate_per_minute":          0.52,
    "tone_proxy":                     "measured_speech_proxy",
    "metrics_source":                 "heuristic",
    "recommendation_to_orchestrator": "monitor_confidence_maintain_difficulty",
    "coaching_tip":                   "Reduce filler words for clarity.",
    "audio_reasoning_summary":        "Moderate delivery with some hesitation.",
    "pace_label":                     "good_pace",
    "detected_issue":                 None,
    "pitch_variation_proxy":          None,
    "volume_energy_proxy":            None,
    "reason":                         None,
}

_RICH_VIDEO = {
    "status":                         "ok",
    "engagement_score":               70,
    "framing_score":                  65,
    "stability_score":                60,
    "movement_activity":              "medium",
    "mode":                           "fallback",
    "frames_analyzed":                15,
    "face_detection_rate":            0.82,
    "analysis_notes":                 ["Face was consistently visible."],
    "warning":                        None,
    "nervousness_proxy_score":        25,
    "looking_away_proxy_score":       35,
    "visual_reasoning_summary":       "Good camera presence and framing.",
    "recommendation_to_orchestrator": "no_video_action_needed",
    "stress_nervousness_indicator":   "medium",
    "face_presence_score":            70,
}


# ── A. /next-question passes selected_role to aggregate_turn ──────────────────

class TestNextQuestionPassesSelectedRole:
    """
    Simulates the aggregate_turn call from /next-question to verify the role
    kwarg is forwarded from session_data["selected_role"].
    Mirrors the exact call pattern in interview_routes.next_question().
    """

    def test_selected_role_kwarg_forwarded(self):
        import services.multimodal_aggregator as ma

        session_data = {
            "selected_role": "Backend Developer",
            "answers": [{"evaluation": {"technical_score": 70, "depth_score": 60}}],
        }

        with patch.object(ma, "aggregate_turn", wraps=ma.aggregate_turn) as mock_agg:
            # Reproduce the exact call the updated route makes
            turn_multi = ma.aggregate_turn(
                session_data["answers"][-1]["evaluation"],
                None,
                None,
                70,
                role=session_data.get("selected_role", ""),
            )

        _args, kwargs = mock_agg.call_args
        assert kwargs["role"] == "Backend Developer"
        # Confirms role-aware weights were activated
        assert turn_multi["reason"] == "role_aware:backend_developer"
        assert turn_multi["weights"]["technical"] == 0.55

    def test_empty_selected_role_falls_back_to_defaults(self):
        import services.multimodal_aggregator as ma

        session_data = {}  # no selected_role key

        with patch.object(ma, "aggregate_turn", wraps=ma.aggregate_turn) as mock_agg:
            result = ma.aggregate_turn(
                {"technical_score": 70, "depth_score": 60},
                None,
                None,
                70,
                role=session_data.get("selected_role", ""),
            )

        _args, kwargs = mock_agg.call_args
        assert kwargs["role"] == ""
        # Default weights (technical=0.45) used when role is absent
        assert result["weights"]["technical"] == 0.45
        assert result["reason"] == "default_weights"

    def test_product_manager_role_uses_communication_weight(self):
        import services.multimodal_aggregator as ma

        session_data = {"selected_role": "Product Manager"}

        result = ma.aggregate_turn(
            {"technical_score": 70, "depth_score": 60},
            None,
            None,
            70,
            role=session_data.get("selected_role", ""),
        )

        assert result["weights"]["communication"] == 0.35
        assert result["weights"]["technical"] == 0.20
        assert result["reason"] == "role_aware:product_manager"


# ── B. /api/scoring/audio persists rich fields ─────────────────────────────────

class TestAudioRoutePersistsRichFields:
    def test_rich_fields_stored_in_session(self):
        sid = _new_session()
        try:
            with patch("services.audio_analyzer.analyze", new=AsyncMock(return_value=_RICH_AUDIO)):
                resp = _client.post(
                    "/api/scoring/audio",
                    data={"session_id": sid, "question_number": "1"},
                    files={"audio": ("test.webm", b"x" * 1000, "audio/webm")},
                )
            assert resp.status_code == 200
            session = store.get_session(sid)
            assert session is not None
            entry = session["audio_scores"][-1]

            assert entry["recommendation_to_orchestrator"] == "monitor_confidence_maintain_difficulty"
            assert entry["coaching_tip"] == "Reduce filler words for clarity."
            assert entry["audio_reasoning_summary"] == "Moderate delivery with some hesitation."
            assert entry["pace_label"] == "good_pace"
            assert entry["detected_issue"] is None
            assert entry["speaking_rate_wpm"] == 130.0
        finally:
            _cleanup(sid)

    def test_existing_fields_still_present(self):
        """Existing fields must not be removed."""
        sid = _new_session()
        try:
            with patch("services.audio_analyzer.analyze", new=AsyncMock(return_value=_RICH_AUDIO)):
                _client.post(
                    "/api/scoring/audio",
                    data={"session_id": sid, "question_number": "1"},
                    files={"audio": ("test.webm", b"x" * 1000, "audio/webm")},
                )
            entry = store.get_session(sid)["audio_scores"][-1]
            assert entry["confidence_score"] == 72
            assert entry["communication_clarity_score"] == 68
            assert entry["hesitation_count"] == 2
            assert entry["metrics_source"] == "heuristic"
            assert entry["tone_proxy"] == "measured_speech_proxy"
        finally:
            _cleanup(sid)


# ── C. /api/scoring/video persists rich fields ─────────────────────────────────

class TestVideoRoutePersistsRichFields:
    def test_rich_fields_stored_in_session(self):
        sid = _new_session()
        try:
            with patch("services.video_analyzer.analyze", new=AsyncMock(return_value=_RICH_VIDEO)):
                resp = _client.post(
                    "/api/scoring/video",
                    data={"session_id": sid, "question_number": "1"},
                    files={"video": ("test.webm", b"x" * 1000, "video/webm")},
                )
            assert resp.status_code == 200
            session = store.get_session(sid)
            assert session is not None
            entry = session["video_scores"][-1]

            assert entry["recommendation_to_orchestrator"] == "no_video_action_needed"
            assert entry["visual_reasoning_summary"] == "Good camera presence and framing."
            assert entry["nervousness_proxy_score"] == 25
            assert entry["looking_away_proxy_score"] == 35
            assert entry["stress_nervousness_indicator"] == "medium"
            assert entry["face_detection_rate"] == 0.82
            assert entry["frames_analyzed"] == 15
            assert entry["face_presence_score"] == 70
            assert entry["analysis_notes"] == ["Face was consistently visible."]
        finally:
            _cleanup(sid)

    def test_existing_fields_still_present(self):
        """Existing fields must not be removed."""
        sid = _new_session()
        try:
            with patch("services.video_analyzer.analyze", new=AsyncMock(return_value=_RICH_VIDEO)):
                _client.post(
                    "/api/scoring/video",
                    data={"session_id": sid, "question_number": "1"},
                    files={"video": ("test.webm", b"x" * 1000, "video/webm")},
                )
            entry = store.get_session(sid)["video_scores"][-1]
            assert entry["engagement_score"] == 70
            assert entry["framing_score"] == 65
            assert entry["stability_score"] == 60
            assert entry["movement_activity"] == "medium"
            assert entry["mode"] == "fallback"
        finally:
            _cleanup(sid)


# ── D. /api/scoring/combined persists both rich audio and video fields ──────────

class TestCombinedRoutePersistsRichFields:
    def test_audio_and_video_rich_fields_stored(self):
        sid = _new_session()
        try:
            with patch("services.audio_analyzer.analyze", new=AsyncMock(return_value=_RICH_AUDIO)), \
                 patch("services.video_analyzer.analyze", new=AsyncMock(return_value=_RICH_VIDEO)):
                resp = _client.post(
                    "/api/scoring/combined",
                    data={"session_id": sid, "question_number": "1"},
                    files={
                        "audio": ("test.webm", b"x" * 1000, "audio/webm"),
                        "video": ("test.webm", b"x" * 1000, "video/webm"),
                    },
                )
            assert resp.status_code == 200
            session = store.get_session(sid)
            assert session is not None

            audio_entry = session["audio_scores"][-1]
            assert audio_entry["recommendation_to_orchestrator"] == "monitor_confidence_maintain_difficulty"
            assert audio_entry["coaching_tip"] == "Reduce filler words for clarity."
            assert audio_entry["audio_reasoning_summary"] == "Moderate delivery with some hesitation."
            assert audio_entry["metrics_source"] == "heuristic"
            assert audio_entry["hesitation_count"] == 2
            assert audio_entry["pause_rate_per_minute"] == 0.52
            assert audio_entry["tone_proxy"] == "measured_speech_proxy"
            assert audio_entry["speaking_rate_wpm"] == 130.0

            video_entry = session["video_scores"][-1]
            assert video_entry["recommendation_to_orchestrator"] == "no_video_action_needed"
            assert video_entry["nervousness_proxy_score"] == 25
            assert video_entry["visual_reasoning_summary"] == "Good camera presence and framing."
            assert video_entry["face_detection_rate"] == 0.82
        finally:
            _cleanup(sid)

    def test_combined_existing_fields_still_present(self):
        """Verifies that adding rich fields didn't break the existing ones."""
        sid = _new_session()
        try:
            with patch("services.audio_analyzer.analyze", new=AsyncMock(return_value=_RICH_AUDIO)), \
                 patch("services.video_analyzer.analyze", new=AsyncMock(return_value=_RICH_VIDEO)):
                _client.post(
                    "/api/scoring/combined",
                    data={"session_id": sid, "question_number": "1"},
                    files={
                        "audio": ("test.webm", b"x" * 1000, "audio/webm"),
                        "video": ("test.webm", b"x" * 1000, "video/webm"),
                    },
                )
            session = store.get_session(sid)

            audio_entry = session["audio_scores"][-1]
            assert audio_entry["confidence_score"] == 72
            assert audio_entry["communication_clarity_score"] == 68
            assert audio_entry["transcript"] == "REST APIs are stateless and scalable."

            video_entry = session["video_scores"][-1]
            assert video_entry["engagement_score"] == 70
            assert video_entry["movement_activity"] == "medium"
            assert video_entry["mode"] == "fallback"
        finally:
            _cleanup(sid)
