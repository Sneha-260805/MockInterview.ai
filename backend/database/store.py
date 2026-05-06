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
