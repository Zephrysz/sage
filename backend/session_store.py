"""
Session store with file-based persistence.

Sessions are kept in memory for fast access and flushed to
/tmp/cefis_sessions.json on every write so they survive uvicorn restarts
(hot-reload during development).
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# Allow override via config (set before importing session_store)
try:
    from config import settings as _settings
    _PERSIST_PATH = _settings.session_store_path
except Exception:
    _PERSIST_PATH = os.environ.get("SESSION_STORE_PATH", "/tmp/cefis_sessions.json")

sessions: dict[str, dict] = {}


def _load() -> None:
    """Load sessions from disk on startup (best-effort)."""
    global sessions
    try:
        if os.path.exists(_PERSIST_PATH):
            with open(_PERSIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                sessions = data
                logger.info("session_store: loaded %d session(s) from %s", len(sessions), _PERSIST_PATH)
    except Exception as exc:
        logger.warning("session_store: could not load persisted sessions — %s", exc)
        sessions = {}


def _save() -> None:
    """Flush sessions to disk (best-effort, non-blocking)."""
    try:
        with open(_PERSIST_PATH, "w", encoding="utf-8") as f:
            json.dump(sessions, f, default=str)
    except Exception as exc:
        logger.warning("session_store: could not persist sessions — %s", exc)


# Load on import
_load()


def get_session(session_id: str) -> dict | None:
    """Return the session dict for the given ID, or None if not found."""
    return sessions.get(session_id)


def create_session(session_id: str, data: dict) -> dict:
    """Create and store a new session, returning the stored dict."""
    sessions[session_id] = data
    _save()
    return sessions[session_id]


def update_session(session_id: str, data: dict) -> dict | None:
    """
    Merge *data* into an existing session and return the updated dict.
    Returns None if the session does not exist.
    """
    if session_id not in sessions:
        return None
    sessions[session_id].update(data)
    _save()
    return sessions[session_id]


def delete_session(session_id: str) -> bool:
    """Remove a session from the store. Returns True if it existed."""
    if session_id in sessions:
        del sessions[session_id]
        _save()
        return True
    return False
