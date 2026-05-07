"""
Fast in-memory key-value store for analyses, role recommendations, and interview sessions.
Always kept in sync with MongoDB so lookups are O(1) on hot paths.
"""

_analyses: dict[str, dict] = {}
_roles: dict[str, dict] = {}
_sessions: dict[str, dict] = {}


def save_analysis(candidate_id: str, data: dict) -> None:
    _analyses[candidate_id] = data


def get_analysis(candidate_id: str) -> dict | None:
    return _analyses.get(candidate_id)


def save_roles(candidate_id: str, data: dict) -> None:
    _roles[candidate_id] = data


def get_roles(candidate_id: str) -> dict | None:
    return _roles.get(candidate_id)


def save_session(session_id: str, data: dict) -> None:
    _sessions[session_id] = data


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def append_audio_score(session_id: str, audio_entry: dict) -> None:
    """Append an audio-analysis result to the session's audio_scores list."""
    session = _sessions.get(session_id)
    if session is not None:
        session.setdefault("audio_scores", []).append(audio_entry)


def append_video_score(session_id: str, video_entry: dict) -> None:
    """Append a video-analysis result to the session's video_scores list."""
    session = _sessions.get(session_id)
    if session is not None:
        session.setdefault("video_scores", []).append(video_entry)
