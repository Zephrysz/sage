"""
In-memory session store.
Uses plain dicts until the Session Pydantic model is defined in task 2.1.
"""

sessions: dict[str, dict] = {}


def get_session(session_id: str) -> dict | None:
    """Return the session dict for the given ID, or None if not found."""
    return sessions.get(session_id)


def create_session(session_id: str, data: dict) -> dict:
    """Create and store a new session, returning the stored dict."""
    sessions[session_id] = data
    return sessions[session_id]


def update_session(session_id: str, data: dict) -> dict | None:
    """
    Merge *data* into an existing session and return the updated dict.
    Returns None if the session does not exist.
    """
    if session_id not in sessions:
        return None
    sessions[session_id].update(data)
    return sessions[session_id]
