"""
Fast in-memory key-value store for analyses, role recommendations, and interview sessions.
Always kept in sync with MongoDB so lookups are O(1) on hot paths.

Persistence: when MongoDB is not available the store auto-saves to a local JSON
file (.session_cache.json in the backend directory) so data survives restarts.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent / ".session_cache.json"

_analyses: dict[str, dict] = {}
_roles: dict[str, dict] = {}
_sessions: dict[str, dict] = {}


# ── Disk persistence ──────────────────────────────────────────────────────────

def _load_from_disk() -> None:
    """Load persisted data from disk on startup (best-effort)."""
    if not _CACHE_FILE.exists():
        return
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        _analyses.update(data.get("analyses", {}))
        _roles.update(data.get("roles", {}))
        _sessions.update(data.get("sessions", {}))
        logger.info(
            "Session cache loaded from disk: %d analyses, %d sessions",
            len(_analyses), len(_sessions),
        )
    except Exception as exc:
        logger.warning("Could not load session cache from disk: %s", exc)


def _save_to_disk() -> None:
    """Persist current in-memory state to disk (best-effort, non-blocking)."""
    try:
        payload = {
            "analyses": _analyses,
            "roles":    _roles,
            "sessions": _sessions,
        }
        _CACHE_FILE.write_text(
            json.dumps(payload, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug("Could not persist session cache to disk: %s", exc)


# Load persisted state on module import (before any route handler runs)
_load_from_disk()


# ── Public API ────────────────────────────────────────────────────────────────

def save_analysis(candidate_id: str, data: dict) -> None:
    _analyses[candidate_id] = data
    _save_to_disk()


def get_analysis(candidate_id: str) -> dict | None:
    return _analyses.get(candidate_id)


def save_roles(candidate_id: str, data: dict) -> None:
    _roles[candidate_id] = data
    _save_to_disk()


def get_roles(candidate_id: str) -> dict | None:
    return _roles.get(candidate_id)


def save_session(session_id: str, data: dict) -> None:
    _sessions[session_id] = data
    _save_to_disk()


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def append_audio_score(session_id: str, audio_entry: dict) -> None:
    """Append an audio-analysis result to the session's audio_scores list."""
    session = _sessions.get(session_id)
    if session is not None:
        session.setdefault("audio_scores", []).append(audio_entry)
        _save_to_disk()


def append_video_score(session_id: str, video_entry: dict) -> None:
    """Append a video-analysis result to the session's video_scores list."""
    session = _sessions.get(session_id)
    if session is not None:
        session.setdefault("video_scores", []).append(video_entry)
        _save_to_disk()
