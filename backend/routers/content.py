from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.content import ContentSource, ContentType
from models.plan import PlanItem
from services import content_service, rag_service
from session_store import get_session

logger = logging.getLogger(__name__)

router = APIRouter()

_RAG_TOP_K = 5
_RAG_THRESHOLD = 0.70


class ContentGenerateRequest(BaseModel):
    plan_item_id: str
    content_type: ContentType


async def _sse_content_stream(
    plan_item: PlanItem,
    content_type: ContentType,
    rag_chunks: list,
) -> AsyncGenerator[str, None]:
    """
    Drive the content generator and wrap output in SSE format.

    Yields SSE-formatted lines, ending with a [DONE] event that carries
    rag_sourced and sources as JSON.
    """
    metadata: dict = {}

    if content_type == ContentType.SUMMARY:
        generator = content_service.generate_summary(plan_item, rag_chunks, metadata)
    else:
        generator = content_service.generate_apostila(plan_item, rag_chunks, metadata)

    async for chunk in generator:
        escaped = chunk.replace("\n", "\\n")
        yield f"data: {escaped}\n\n"

    rag_sourced: bool = metadata.get("rag_sourced", False)
    sources: list[ContentSource] = metadata.get("sources", [])

    done_payload = {
        "rag_sourced": rag_sourced,
        "sources": [s.model_dump() for s in sources],
    }
    yield f"data: [DONE] {json.dumps(done_payload, ensure_ascii=False)}\n\n"


@router.post("/generate")
async def generate_content(
    body: ContentGenerateRequest = Body(...),
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> StreamingResponse:
    """
    Generate a summary or apostila for a study plan item, streamed via SSE.

    Steps:
    1. Validate session exists.
    2. Find the plan item in the session's study_plan.
    3. Query RAG with the item's topic (and course_id if available).
    4. Stream generated content chunks.
    5. Send final [DONE] event with rag_sourced and sources.
    """
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    study_plan = session.get("study_plan")
    plan_item_data: dict | None = None

    if study_plan:
        items = study_plan.get("items", [])
        for item in items:
            item_id = str(item.get("id", ""))
            if item_id == body.plan_item_id:
                plan_item_data = item
                break

    if plan_item_data is None:
        raise HTTPException(status_code=404, detail="Plan item not found in session")

    try:
        plan_item = PlanItem(**plan_item_data)
    except Exception as exc:
        logger.error("Failed to parse plan item: %s — %s", plan_item_data, exc)
        raise HTTPException(status_code=500, detail="Invalid plan item data")

    course_id: str | None = plan_item.course_id
    query_text = plan_item.title

    try:
        rag_chunks = await rag_service.query_rag(
            query_text=query_text,
            course_id=course_id,
            top_k=_RAG_TOP_K,
            threshold=_RAG_THRESHOLD,
        )
    except Exception as exc:
        logger.warning("RAG query failed, proceeding without context: %s", exc)
        rag_chunks = []

    return StreamingResponse(
        _sse_content_stream(plan_item, body.content_type, rag_chunks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── TTS voices endpoint ───────────────────────────────────────────────────────

@router.get("/tts/voices")
async def list_tts_voices() -> dict:
    """Return available TTS voices."""
    from services.gemini_service import TTS_VOICES
    return {"voices": TTS_VOICES}


# ── Podcast script + TTS ──────────────────────────────────────────────────────

class PodcastRequest(BaseModel):
    plan_item_id: str
    voice_name: str = "Achernar"
    speaking_rate: float = 1.0


@router.post("/podcast/script")
async def generate_podcast_script(
    body: PodcastRequest = Body(...),
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> StreamingResponse:
    """
    Generate a podcast script for a plan item, streamed via SSE.
    Script length scales with the user's session time_available.
    """
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    study_plan = session.get("study_plan")
    plan_item_data: dict | None = None
    if study_plan:
        for item in study_plan.get("items", []):
            if str(item.get("id", "")) == body.plan_item_id:
                plan_item_data = item
                break

    if plan_item_data is None:
        raise HTTPException(status_code=404, detail="Plan item not found")

    try:
        plan_item = PlanItem(**plan_item_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Invalid plan item: {exc}")

    # Scale podcast duration to session time (capped at 10 min = 1300 words)
    profile_data = session.get("profile") or {}
    time_available: int = int(profile_data.get("time_available", 30))
    # ~130 words/min, cap at 10 min, floor at 2 min
    target_minutes = max(2, min(10, time_available))
    target_words = target_minutes * 130

    try:
        rag_chunks = await rag_service.query_rag(
            query_text=plan_item.title,
            course_id=plan_item.course_id,
            top_k=_RAG_TOP_K,
            threshold=_RAG_THRESHOLD,
        )
    except Exception:
        rag_chunks = []

    metadata: dict = {}
    accumulated_script: list[str] = []

    async def _stream():
        async for chunk in content_service.generate_podcast_script(
            plan_item, rag_chunks, metadata, target_words=target_words
        ):
            accumulated_script.append(chunk)
            escaped = chunk.replace("\n", "\\n")
            yield f"data: {escaped}\n\n"

        from session_store import update_session
        from datetime import datetime
        full_script = "".join(accumulated_script)
        podcast_scripts = session.get("podcast_scripts") or {}
        podcast_scripts[body.plan_item_id] = {
            "script": full_script,
            "voice_name": body.voice_name,
        }
        update_session(x_session_id, {
            "podcast_scripts": podcast_scripts,
            "updated_at": datetime.utcnow().isoformat(),
        })

        done_payload = {
            "rag_sourced": metadata.get("rag_sourced", False),
            "sources": [s.model_dump() for s in metadata.get("sources", [])],
        }
        yield f"data: [DONE] {json.dumps(done_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/podcast/synthesize")
async def synthesize_podcast(
    body: PodcastRequest = Body(...),
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> StreamingResponse:
    """
    Synthesize the stored podcast script to MP3 audio.
    Returns the MP3 as a streaming response.
    """
    from services.gemini_service import synthesize_speech

    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    podcast_scripts = session.get("podcast_scripts") or {}
    entry = podcast_scripts.get(body.plan_item_id)
    if not entry:
        raise HTTPException(status_code=404, detail="No script found — generate script first")

    script_text = entry.get("script", "")
    voice_name = body.voice_name or entry.get("voice_name", "Achernar")

    try:
        audio_bytes, mime_type = await synthesize_speech(
            text=script_text,
            voice_name=voice_name,
            language_code="pt-BR",
            speaking_rate=body.speaking_rate,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    ext = "wav" if mime_type == "audio/wav" else "mp3"
    return StreamingResponse(
        iter([audio_bytes]),
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="podcast_{body.plan_item_id}.{ext}"',
            "Content-Length": str(len(audio_bytes)),
        },
    )
