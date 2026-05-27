import uuid
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from models.session import Profile, Session, SessionState
from services.cefis_service import (
    CefisAuthError,
    CefisTimeoutError,
    login as cefis_login,
)
from session_store import create_session, get_session, update_session

router = APIRouter()


class SessionInitRequest(BaseModel):
    email: str
    password: str


@router.post("/init")
async def session_init(body: SessionInitRequest) -> dict:
    """
    Authenticate with CEFIS using email + password.
    CEFIS returns an API key which is stored in the session for all
    subsequent calls — the frontend never needs to handle the key directly.
    """
    try:
        result = await cefis_login(body.email, body.password)
    except CefisAuthError:
        return {"error": "auth_failed"}
    except CefisTimeoutError:
        return {"error": "timeout"}

    # Response shape: { "data": { "key": "...", "user": { ... } } }
    data = result.get("data", {})
    api_key = data.get("key")
    user = data.get("user")

    if not api_key:
        return {"error": "auth_failed"}

    session_id = str(uuid.uuid4())
    now = datetime.utcnow()

    session_data = Session(
        id=uuid.UUID(session_id),
        state=SessionState.ONBOARDING,
        user=user,
        created_at=now,
        updated_at=now,
    )

    # Store the key in the session — used for all CEFIS API calls
    session_dict = session_data.model_dump(mode="json")
    session_dict["cefis_api_key"] = api_key

    create_session(session_id, session_dict)

    # Only send the name to the frontend — avoid leaking internal user fields
    user_name = ""
    if isinstance(user, dict):
        user_name = str(user.get("name") or user.get("full_name") or user.get("username") or "")

    return {
        "session_id": session_id,
        "user": {"name": user_name},
    }


@router.post("/confirm-profile")
async def confirm_profile(
    profile: Profile,
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> dict:
    """
    Validate the session, store the profile, and transition state to DIAGNOSIS.
    """
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    updated = update_session(
        x_session_id,
        {
            "profile": profile.model_dump(mode="json"),
            "state": SessionState.DIAGNOSIS.value,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )

    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"ok": True}


class UpdateStateRequest(BaseModel):
    state: str


@router.post("/state")
async def update_state(
    body: UpdateStateRequest,
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> dict:
    """
    Update the session state. Used by the frontend when navigating between
    views (e.g. transitioning to STUDY_MODE when entering the study page).
    Only allows transitions to STUDY_MODE or PLAN_READY from valid states.
    """
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        new_state = SessionState(body.state)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid state: {body.state}")

    allowed = {SessionState.STUDY_MODE, SessionState.PLAN_READY}
    if new_state not in allowed:
        raise HTTPException(status_code=422, detail=f"Cannot transition to state: {body.state}")

    update_session(
        x_session_id,
        {
            "state": new_state.value,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )
    return {"ok": True}
