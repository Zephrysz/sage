from __future__ import annotations

import logging
from typing import AsyncGenerator

from models.content import ContentSource
from models.plan import PlanItem
from services.rag_service import RagChunk
from services import gemini_service

logger = logging.getLogger(__name__)


def _build_rag_context(rag_chunks: list[RagChunk]) -> str:
    """Format RAG chunks into a context block for the Gemini prompt."""
    parts = []
    for i, chunk in enumerate(rag_chunks, start=1):
        parts.append(
            f"[Trecho {i} — {chunk.course_name} / {chunk.lesson_name}]\n{chunk.content}"
        )
    return "\n\n".join(parts)


def _extract_sources(rag_chunks: list[RagChunk]) -> list[ContentSource]:
    """Deduplicate and return ContentSource objects from the chunks used."""
    seen: set[tuple[str, str]] = set()
    sources: list[ContentSource] = []
    for chunk in rag_chunks:
        key = (chunk.course_name, chunk.lesson_name)
        if key not in seen:
            seen.add(key)
            sources.append(ContentSource(course_name=chunk.course_name, lesson_name=chunk.lesson_name))
    return sources



async def generate_summary(
    plan_item: PlanItem,
    rag_chunks: list[RagChunk] | None,
    metadata: dict,
) -> AsyncGenerator[str, None]:
    """
    Generate a 250–350 word summary for the given plan item.

    Yields text chunks for SSE streaming.
    Populates *metadata* dict with:
      - rag_sourced (bool)
      - sources (list[ContentSource])

    Args:
        plan_item: The study plan item being summarised.
        rag_chunks: Relevant transcript chunks from RAG (may be empty/None).
        metadata: Mutable dict that will be populated with rag_sourced and sources.
    """
    chunks = rag_chunks or []
    rag_sourced = bool(chunks)
    sources = _extract_sources(chunks)

    metadata["rag_sourced"] = rag_sourced
    metadata["sources"] = sources

    if rag_sourced:
        context_block = _build_rag_context(chunks)
        system_prompt = (
            "Você é um tutor educacional especializado. "
            "Use os trechos de transcrição fornecidos como base principal do conteúdo. "
            "Escreva em português brasileiro, de forma clara e didática."
        )
        user_prompt = (
            f"Com base nos trechos abaixo, escreva um resumo sobre o tópico '{plan_item.title}'. "
            f"O resumo deve ter entre 250 e 350 palavras, ser coeso e cobrir os pontos principais do material.\n\n"
            f"TRECHOS DE REFERÊNCIA:\n{context_block}"
        )
    else:
        system_prompt = (
            "Você é um tutor educacional especializado. "
            "Escreva em português brasileiro, de forma clara e didática."
        )
        user_prompt = (
            f"Escreva um resumo sobre o tópico '{plan_item.title}'. "
            f"O resumo deve ter entre 250 e 350 palavras, ser coeso e cobrir os pontos principais do tema."
        )

    async for chunk in gemini_service.chat_turn(
        history=[],
        system_prompt=system_prompt,
        user_message=user_prompt,
    ):
        yield chunk


async def generate_apostila(
    plan_item: PlanItem,
    rag_chunks: list[RagChunk] | None,
    metadata: dict,
) -> AsyncGenerator[str, None]:
    """
    Generate a structured 400–1200 word apostila for the given plan item.

    Sections: introdução, conceitos principais, exemplos práticos, pontos de atenção.

    Yields text chunks for SSE streaming.
    Populates *metadata* dict with:
      - rag_sourced (bool)
      - sources (list[ContentSource])

    Args:
        plan_item: The study plan item being covered.
        rag_chunks: Relevant transcript chunks from RAG (may be empty/None).
        metadata: Mutable dict that will be populated with rag_sourced and sources.
    """
    chunks = rag_chunks or []
    rag_sourced = bool(chunks)
    sources = _extract_sources(chunks)

    metadata["rag_sourced"] = rag_sourced
    metadata["sources"] = sources

    if rag_sourced:
        context_block = _build_rag_context(chunks)
        system_prompt = (
            "Você é um tutor educacional especializado em criar material didático estruturado. "
            "Use os trechos de transcrição fornecidos como base principal do conteúdo. "
            "Escreva em português brasileiro, de forma clara, didática e bem organizada."
        )
        user_prompt = (
            f"Com base nos trechos abaixo, crie uma apostila completa sobre o tópico '{plan_item.title}'. "
            f"A apostila deve ter entre 400 e 1200 palavras e conter exatamente as seguintes seções:\n\n"
            f"## Introdução\n"
            f"## Conceitos Principais\n"
            f"## Exemplos Práticos\n"
            f"## Pontos de Atenção\n\n"
            f"Use markdown para formatar as seções. Seja didático e aprofundado.\n\n"
            f"TRECHOS DE REFERÊNCIA:\n{context_block}"
        )
    else:
        system_prompt = (
            "Você é um tutor educacional especializado em criar material didático estruturado. "
            "Escreva em português brasileiro, de forma clara, didática e bem organizada."
        )
        user_prompt = (
            f"Crie uma apostila completa sobre o tópico '{plan_item.title}'. "
            f"A apostila deve ter entre 400 e 1200 palavras e conter exatamente as seguintes seções:\n\n"
            f"## Introdução\n"
            f"## Conceitos Principais\n"
            f"## Exemplos Práticos\n"
            f"## Pontos de Atenção\n\n"
            f"Use markdown para formatar as seções. Seja didático e aprofundado."
        )

    async for chunk in gemini_service.chat_turn(
        history=[],
        system_prompt=system_prompt,
        user_message=user_prompt,
    ):
        yield chunk
