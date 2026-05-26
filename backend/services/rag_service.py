"""
RAG service — queries pgvector via Supabase RPC.

Provides `query_rag` which embeds a query text and retrieves the most
semantically similar transcript chunks from Supabase, optionally filtered
by course.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel
from supabase import Client, create_client

from config import settings
from services import gemini_service

logger = logging.getLogger(__name__)

_supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)


class RagChunk(BaseModel):
    course_name: str
    lesson_name: str
    content: str
    similarity: float


async def query_rag(
    query_text: str,
    course_id: str | None = None,
    top_k: int = 5,
    threshold: float = 0.70,
) -> list[RagChunk]:
    """
    Retrieve the most relevant transcript chunks for *query_text*.

    Strategy:
    1. Embed *query_text* via Gemini.
    2. If *course_id* is provided, call ``match_chunks_by_course`` RPC.
       If that returns no results, fall back to ``match_chunks_global``.
    3. If *course_id* is absent, call ``match_chunks_global`` directly.
    4. Map raw rows to ``RagChunk`` objects and return them.

    On any error (embed failure, RPC failure) the function logs the
    exception and returns an empty list so callers can degrade gracefully.

    Args:
        query_text: Natural-language query to embed and search.
        course_id:  Optional course identifier to scope the search.
        top_k:      Maximum number of chunks to return (default 5).
        threshold:  Minimum cosine-similarity score (default 0.70).

    Returns:
        A list of ``RagChunk`` objects ordered by descending similarity.
    """
    try:
        embedding = await gemini_service.embed(query_text)
    except Exception as exc:
        logger.error("query_rag: embedding failed — %s", exc)
        return []

    try:
        chunks = _fetch_chunks(
            embedding=embedding,
            course_id=course_id,
            top_k=top_k,
            threshold=threshold,
        )
    except Exception as exc:
        logger.error("query_rag: Supabase RPC failed — %s", exc)
        return []

    return _map_chunks(chunks)


def _fetch_chunks(
    embedding: list[float],
    course_id: str | None,
    top_k: int,
    threshold: float,
) -> list[dict]:
    """
    Call the appropriate Supabase RPC and return raw row dicts.

    Falls back to the global index when a course-scoped query returns
    no results.
    """
    if course_id:
        rows = _rpc_by_course(embedding, str(course_id), top_k, threshold)
        if rows:
            return rows
        logger.debug(
            "query_rag: no results for course_id=%s, falling back to global index",
            course_id,
        )

    return _rpc_global(embedding, top_k, threshold)


def _rpc_by_course(
    embedding: list[float],
    course_id: str,
    top_k: int,
    threshold: float,
) -> list[dict]:
    result = _supabase.rpc(
        "match_chunks_by_course",
        {
            "query_embedding": embedding,
            "course_id_filter": course_id,
            "match_threshold": threshold,
            "match_count": top_k,
        },
    ).execute()
    return result.data or []


def _rpc_global(
    embedding: list[float],
    top_k: int,
    threshold: float,
) -> list[dict]:
    result = _supabase.rpc(
        "match_chunks_global",
        {
            "query_embedding": embedding,
            "match_threshold": threshold,
            "match_count": top_k,
        },
    ).execute()
    return result.data or []


def _map_chunks(rows: list[dict]) -> list[RagChunk]:
    """Convert raw Supabase rows to ``RagChunk`` objects, skipping malformed rows."""
    chunks: list[RagChunk] = []
    for row in rows:
        try:
            chunks.append(
                RagChunk(
                    course_name=row["course_name"],
                    lesson_name=row["lesson_name"],
                    content=row["content"],
                    similarity=float(row["similarity"]),
                )
            )
        except Exception as exc:
            logger.warning("query_rag: skipping malformed row %s — %s", row, exc)
    return chunks
