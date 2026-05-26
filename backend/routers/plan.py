from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from models.plan import StudyPlan, PlanItemType
from models.session import SessionState
from services import cefis_service, plan_service, rag_service
from services.cefis_service import (
    CefisAuthError,
    CefisServerError,
    CefisTimeoutError,
)
from services.rag_service import RagChunk
from session_store import get_session, update_session

logger = logging.getLogger(__name__)

router = APIRouter()

_PLAN_STATES = {SessionState.PLAN_READY, SessionState.STUDY_MODE}


class AdjustPlanRequest(BaseModel):
    new_time_available: int


def _get_api_key(session: dict) -> str:
    """Extract the CEFIS API key stored in the session at login time."""
    return session.get("cefis_api_key", "")


async def _fetch_courses(api_key: str, time_available: int) -> list[dict]:
    """
    Fetch the CEFIS course catalog, applying quick_filter when time_available ≤ 60.
    Returns an empty list on any CEFIS error (Req 4.6).
    """
    quick_filter = time_available <= 60
    try:
        result = await cefis_service.get_courses(api_key, quick_filter=quick_filter)
        if isinstance(result, dict):
            courses = result.get("data") or result.get("courses") or []
        elif isinstance(result, list):
            courses = result
        else:
            courses = []
        return courses
    except (CefisAuthError, CefisServerError, CefisTimeoutError) as exc:
        logger.warning("_fetch_courses: CEFIS error — %s", exc)
        return []
    except Exception as exc:
        logger.error("_fetch_courses: unexpected error — %s", exc)
        return []


async def _fetch_rag_chunks(gaps: list[dict]) -> list[RagChunk]:
    """
    Query RAG for each gap topic and collect all returned chunks.
    Individual failures are silently skipped (empty list returned for that gap).
    """
    all_chunks: list[RagChunk] = []
    for gap in gaps:
        topic = gap.get("topic", "")
        if not topic:
            continue
        try:
            chunks = await rag_service.query_rag(topic, course_id=None, top_k=5)
            all_chunks.extend(chunks)
        except Exception as exc:
            logger.warning("_fetch_rag_chunks: RAG query failed for topic '%s' — %s", topic, exc)
    return all_chunks


async def _enrich_cefis_items(plan: StudyPlan, api_key: str) -> None:
    """
    For each CEFIS_COURSE item in the plan, fetch course details and lessons
    from the CEFIS API and store them in course_details.
    Failures are logged and the item is left with whatever details it already has.
    """
    for item in plan.items:
        if item.type != PlanItemType.CEFIS_COURSE or not item.course_id:
            continue
        try:
            detail = await cefis_service.get_course_detail(api_key, item.course_id)
            lessons = await cefis_service.get_course_lessons(api_key, item.course_id)
            merged: dict = {}
            if isinstance(detail, dict):
                merged.update(detail)
            if isinstance(lessons, list):
                merged["lessons"] = lessons
            elif isinstance(lessons, dict):
                merged["lessons"] = lessons.get("data") or lessons.get("lessons") or []
            item.course_details = merged
        except (CefisAuthError, CefisServerError, CefisTimeoutError) as exc:
            logger.warning(
                "_enrich_cefis_items: failed to enrich course_id=%s — %s",
                item.course_id,
                exc,
            )
        except Exception as exc:
            logger.error(
                "_enrich_cefis_items: unexpected error for course_id=%s — %s",
                item.course_id,
                exc,
            )


async def _mark_certificates(plan: StudyPlan, api_key: str) -> None:
    """
    Fetch the student's certificates and mark has_certificate=True on plan items
    whose course topic matches a certificate.
    On any error, log and continue without certificate indicators.
    """
    try:
        certs_response = await cefis_service.get_certificates(api_key)
        if isinstance(certs_response, dict):
            certs = (
                certs_response.get("data")
                or certs_response.get("certificates")
                or []
            )
        elif isinstance(certs_response, list):
            certs = certs_response
        else:
            certs = []
    except (CefisAuthError, CefisServerError, CefisTimeoutError) as exc:
        logger.warning("_mark_certificates: CEFIS error fetching certificates — %s", exc)
        return
    except Exception as exc:
        logger.error("_mark_certificates: unexpected error — %s", exc)
        return

    if not certs:
        return

    cert_course_ids: set[str] = set()
    cert_titles: set[str] = set()
    for cert in certs:
        if not isinstance(cert, dict):
            continue
        cid = cert.get("course_id") or cert.get("courseId") or cert.get("id")
        if cid:
            cert_course_ids.add(str(cid))
        title = (cert.get("title") or cert.get("course_title") or cert.get("name") or "").lower()
        if title:
            cert_titles.add(title)

    for item in plan.items:
        if item.type != PlanItemType.CEFIS_COURSE:
            continue
        if item.course_id and item.course_id in cert_course_ids:
            item.has_certificate = True
            continue
        item_title_lower = item.title.lower()
        for cert_title in cert_titles:
            if cert_title and (cert_title in item_title_lower or item_title_lower in cert_title):
                item.has_certificate = True
                break


def _session_to_model(session: dict):
    """
    Reconstruct a lightweight Session-like object from the raw session dict
    so that plan_service functions can access .profile and .diagnosis.
    """
    from models.session import Session, Profile, ExperienceLevel, LearningStyle
    from models.diagnosis import DiagnosisResult, DiagnosisLevel, Gap
    import uuid
    from datetime import datetime as dt

    profile_data = session.get("profile")
    diagnosis_data = session.get("diagnosis")

    profile = None
    if profile_data:
        try:
            profile = Profile(
                goal=profile_data["goal"],
                level=ExperienceLevel(profile_data["level"]),
                time_available=int(profile_data["time_available"]),
                learning_style=LearningStyle(profile_data["learning_style"]),
            )
        except Exception as exc:
            logger.error("_session_to_model: failed to build Profile — %s", exc)

    diagnosis = None
    if diagnosis_data:
        try:
            gaps = [
                Gap(
                    topic=g["topic"],
                    is_critical=g.get("is_critical", False),
                    wrong_count=g.get("wrong_count", 0),
                )
                for g in (diagnosis_data.get("gaps") or [])
            ]
            diagnosis = DiagnosisResult(
                level=DiagnosisLevel(diagnosis_data["level"]),
                score=float(diagnosis_data.get("score", 0.0)),
                gaps=gaps,
            )
        except Exception as exc:
            logger.error("_session_to_model: failed to build DiagnosisResult — %s", exc)

    study_plan_data = session.get("study_plan")
    study_plan = None
    if study_plan_data:
        try:
            study_plan = StudyPlan(**study_plan_data)
        except Exception:
            pass

    session_id = session.get("id", str(uuid.uuid4()))
    now = dt.utcnow()

    return Session(
        id=uuid.UUID(str(session_id)) if session_id else uuid.uuid4(),
        state=SessionState(session.get("state", SessionState.PLAN_READY.value)),
        user=session.get("user"),
        profile=profile,
        diagnosis=diagnosis,
        study_plan=study_plan,
        chat_history=[],
        current_course_id=session.get("current_course_id"),
        created_at=session.get("created_at", now),
        updated_at=session.get("updated_at", now),
    )


@router.get("")
async def get_plan(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> dict:
    """
    Build and return the student's study plan.

    Steps:
    1. Validate session exists and is in PLAN_READY or STUDY_MODE.
    2. Fetch CEFIS courses (graceful fallback to empty list on error).
    3. Query RAG for each diagnosed gap.
    4. Build the plan via plan_service.build_plan.
    5. Enrich CEFIS_COURSE items with course details and lessons.
    6. Mark has_certificate on items where the student holds a certificate.
    7. Persist the plan in the session and return it.
    """
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    state = SessionState(session.get("state", ""))
    if state not in _PLAN_STATES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot generate plan in state '{state.value}'. "
                "Complete the diagnosis first."
            ),
        )

    profile_data = session.get("profile") or {}
    time_available: int = int(profile_data.get("time_available", 60))
    diagnosis_data = session.get("diagnosis") or {}
    gaps: list[dict] = diagnosis_data.get("gaps") or []

    api_key = _get_api_key(session)

    courses = await _fetch_courses(api_key, time_available)

    rag_chunks = await _fetch_rag_chunks(gaps)

    session_model = _session_to_model(session)
    plan = await plan_service.build_plan(session_model, courses, rag_chunks)

    await _enrich_cefis_items(plan, api_key)

    await _mark_certificates(plan, api_key)

    update_session(
        x_session_id,
        {
            "study_plan": plan.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat(),
        },
    )

    return plan.model_dump(mode="json")

@router.post("/adjust")
async def adjust_plan(
    body: AdjustPlanRequest,
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> dict:
    """
    Recalculate the study plan with a new time_available value.

    Steps:
    1. Validate session exists.
    2. Validate new_time_available > 0 (Req 5.4).
    3. Re-fetch courses and RAG chunks.
    4. Call plan_service.adjust_plan.
    5. Persist updated plan in session.
    6. Return new StudyPlan.
    """
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if body.new_time_available < 1:
        raise HTTPException(
            status_code=422,
            detail="new_time_available deve ser um número inteiro maior que zero.",
        )

    diagnosis_data = session.get("diagnosis") or {}
    gaps: list[dict] = diagnosis_data.get("gaps") or []
    api_key = _get_api_key(session)

    courses = await _fetch_courses(api_key, body.new_time_available)

    rag_chunks = await _fetch_rag_chunks(gaps)

    session_model = _session_to_model(session)
    try:
        plan = await plan_service.adjust_plan(
            session_model,
            body.new_time_available,
            courses,
            rag_chunks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await _enrich_cefis_items(plan, api_key)
    await _mark_certificates(plan, api_key)

    profile_data = dict(session.get("profile") or {})
    profile_data["time_available"] = body.new_time_available

    update_session(
        x_session_id,
        {
            "study_plan": plan.model_dump(mode="json"),
            "profile": profile_data,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )

    return plan.model_dump(mode="json")
