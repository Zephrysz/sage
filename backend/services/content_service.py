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
    chunks = rag_chunks or []
    rag_sourced = bool(chunks)
    sources = _extract_sources(chunks)

    metadata["rag_sourced"] = rag_sourced
    metadata["sources"] = sources

    if rag_sourced:
        context_block = _build_rag_context(chunks)
        system_prompt = (
            "Você é um tutor educacional especializado. "
            "Você SEMPRE escreve em português brasileiro, sem exceção. "
            "Use os trechos de transcrição fornecidos como base principal do conteúdo. "
            "REGRA CRÍTICA: Retorne APENAS o texto do resumo, sem introduções como 'Aqui está o resumo:', "
            "'Claro!', 'Com base nos trechos fornecidos,' ou qualquer frase de abertura. "
            "Comece diretamente com o conteúdo do resumo."
        )
        user_prompt = (
            f"Escreva um resumo em português brasileiro sobre o tópico '{plan_item.title}'. "
            f"O resumo deve ter entre 250 e 350 palavras, ser coeso e cobrir os pontos principais do material. "
            f"Retorne apenas o texto do resumo, sem títulos, cabeçalhos ou frases introdutórias.\n\n"
            f"TRECHOS DE REFERÊNCIA:\n{context_block}"
        )
    else:
        system_prompt = (
            "Você é um tutor educacional especializado. "
            "Você SEMPRE escreve em português brasileiro, sem exceção. "
            "REGRA CRÍTICA: Retorne APENAS o texto do resumo, sem introduções como 'Aqui está o resumo:', "
            "'Claro!', ou qualquer frase de abertura. Comece diretamente com o conteúdo."
        )
        user_prompt = (
            f"Escreva um resumo em português brasileiro sobre o tópico '{plan_item.title}'. "
            f"O resumo deve ter entre 250 e 350 palavras, ser coeso e cobrir os pontos principais do tema. "
            f"Retorne apenas o texto do resumo, sem títulos, cabeçalhos ou frases introdutórias."
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
    chunks = rag_chunks or []
    rag_sourced = bool(chunks)
    sources = _extract_sources(chunks)

    metadata["rag_sourced"] = rag_sourced
    metadata["sources"] = sources

    if rag_sourced:
        context_block = _build_rag_context(chunks)
        system_prompt = (
            "Você é um tutor educacional especializado em criar material didático estruturado. "
            "Você SEMPRE escreve em português brasileiro, sem exceção. "
            "Use os trechos de transcrição fornecidos como base principal do conteúdo. "
            "REGRA CRÍTICA: Retorne APENAS o conteúdo da apostila em markdown, começando diretamente "
            "com a primeira seção '## Introdução'. Nunca adicione frases como 'Aqui está a apostila:', "
            "'Claro!', 'Com base nos trechos,' ou qualquer introdução antes do conteúdo."
        )
        user_prompt = (
            f"Crie uma apostila completa em português brasileiro sobre o tópico '{plan_item.title}'. "
            f"A apostila deve ter entre 400 e 1200 palavras e conter exatamente as seguintes seções:\n\n"
            f"## Introdução\n"
            f"## Conceitos Principais\n"
            f"## Exemplos Práticos\n"
            f"## Pontos de Atenção\n\n"
            f"Use markdown para formatar as seções. Seja didático e aprofundado. "
            f"Comece diretamente com '## Introdução'.\n\n"
            f"TRECHOS DE REFERÊNCIA:\n{context_block}"
        )
    else:
        system_prompt = (
            "Você é um tutor educacional especializado em criar material didático estruturado. "
            "Você SEMPRE escreve em português brasileiro, sem exceção. "
            "REGRA CRÍTICA: Retorne APENAS o conteúdo da apostila em markdown, começando diretamente "
            "com a primeira seção '## Introdução'. Nunca adicione frases introdutórias antes do conteúdo."
        )
        user_prompt = (
            f"Crie uma apostila completa em português brasileiro sobre o tópico '{plan_item.title}'. "
            f"A apostila deve ter entre 400 e 1200 palavras e conter exatamente as seguintes seções:\n\n"
            f"## Introdução\n"
            f"## Conceitos Principais\n"
            f"## Exemplos Práticos\n"
            f"## Pontos de Atenção\n\n"
            f"Use markdown para formatar as seções. Seja didático e aprofundado. "
            f"Comece diretamente com '## Introdução'."
        )

    async for chunk in gemini_service.chat_turn(
        history=[],
        system_prompt=system_prompt,
        user_message=user_prompt,
    ):
        yield chunk


async def generate_podcast_script(
    plan_item: PlanItem,
    rag_chunks: list[RagChunk] | None,
    metadata: dict,
    target_words: int = 390,
) -> AsyncGenerator[str, None]:
    """
    Generate a podcast script scaled to target_words (~130 wpm).
    """
    chunks = rag_chunks or []
    rag_sourced = bool(chunks)
    sources = _extract_sources(chunks)

    metadata["rag_sourced"] = rag_sourced
    metadata["sources"] = sources

    target_minutes = round(target_words / 130, 1)
    word_instruction = (
        f"O roteiro deve ter aproximadamente {target_words} palavras "
        f"(~{target_minutes} minutos de áudio a 130 palavras por minuto)."
    )

    base_instruction = (
        f"Tom: conversacional, didático, como se estivesse explicando para um amigo. "
        f"Inclua uma introdução cativante, os pontos principais e uma conclusão motivadora. "
        f"Escreva apenas o texto que será narrado, sem indicações de cena, rubricas ou formatação markdown."
    )

    if rag_sourced:
        context_block = _build_rag_context(chunks)
        system_prompt = (
            "Você é um roteirista de podcasts educacionais. "
            "Você SEMPRE escreve em português brasileiro, sem exceção. "
            "Crie roteiros envolventes, conversacionais e fáceis de ouvir. "
            "REGRA CRÍTICA: Retorne APENAS o texto do roteiro que será narrado, sem nenhuma introdução "
            "como 'Aqui está o roteiro:', 'Claro!', 'Com base nos trechos,' ou qualquer frase antes do conteúdo. "
            "Sem indicações de cena, rubricas, títulos ou formatação markdown. Apenas o texto narrado."
        )
        user_prompt = (
            f"Crie um roteiro de podcast em português brasileiro sobre '{plan_item.title}'. "
            f"{word_instruction} {base_instruction}\n\n"
            f"TRECHOS DE REFERÊNCIA:\n{context_block}"
        )
    else:
        system_prompt = (
            "Você é um roteirista de podcasts educacionais. "
            "Você SEMPRE escreve em português brasileiro, sem exceção. "
            "Crie roteiros envolventes, conversacionais e fáceis de ouvir. "
            "REGRA CRÍTICA: Retorne APENAS o texto do roteiro que será narrado, sem nenhuma introdução "
            "como 'Aqui está o roteiro:', 'Claro!', ou qualquer frase antes do conteúdo. "
            "Sem indicações de cena, rubricas, títulos ou formatação markdown. Apenas o texto narrado."
        )
        user_prompt = (
            f"Crie um roteiro de podcast em português brasileiro sobre '{plan_item.title}'. "
            f"{word_instruction} {base_instruction}"
        )

    async for chunk in gemini_service.chat_turn(
        history=[],
        system_prompt=system_prompt,
        user_message=user_prompt,
    ):
        yield chunk
