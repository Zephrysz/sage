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
