from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

from config import settings
from models.diagnosis import Gap
from models.plan import PlanItem, PlanItemType, StudyPlan
from services.rag_service import RagChunk

if TYPE_CHECKING:
    from models.session import Session

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)
_CHAT_MODEL = "gemini-2.5-flash"

def _base_item_limit(time_available: int) -> int:
    """Return the base maximum number of plan items for the given time budget."""
    if time_available <= 15:
        return 2
    if time_available <= 30:
        return 3
    if time_available <= 60:
        return 4
    return 6


def _item_limit(time_available: int, has_critical_gaps: bool) -> int:
    """
    Return the effective item limit, adding up to 2 extra for critical gaps.
    Hard cap is 8 items total (Req 5.2).
    """
    base = _base_item_limit(time_available)
    if has_critical_gaps:
        return min(base + 2, 8)
    return base


_RELEVANCE_THRESHOLD = 0.50

async def _filter_courses_with_gemini(
    courses: list[dict],
    rag_chunks: list[RagChunk],
    goal: str,
    area: str,
    gaps: list[Gap],
) -> list[tuple[dict, float]]:
    """
    Use Gemini to filter and rank the CEFIS course catalog based on:
    - The student's goal, area, and diagnosed gaps
    - RAG chunks that represent relevant content topics

    Returns courses sorted by relevance score (0.0–1.0), filtered to those
    Gemini considers relevant. Falls back to all courses if Gemini fails.
    """
    import json as _json
    from google.genai import types as gtypes

    if not courses:
        return []

    # Build context from RAG chunks
    rag_context = ""
    if rag_chunks:
        rag_context = "Tópicos relevantes encontrados no índice de conteúdo:\n" + "\n".join(
            f"- {c.course_name}: {c.lesson_name} (similaridade: {c.similarity:.2f})"
            for c in rag_chunks[:10]
        )

    gap_topics = ", ".join(g.topic for g in gaps) if gaps else "nenhuma lacuna identificada"

    course_list = "\n".join(
        f"{i+1}. id={c.get('id')} title=\"{c.get('title') or c.get('name', '')}\""
        for i, c in enumerate(courses)
    )

    prompt = (
        f"Você é um especialista em educação profissional. "
        f"Dado o perfil do aluno abaixo, avalie quais cursos do catálogo são relevantes.\n\n"
        f"PERFIL DO ALUNO:\n"
        f"- Área: {area}\n"
        f"- Objetivo: {goal}\n"
        f"- Lacunas identificadas: {gap_topics}\n\n"
        f"{rag_context}\n\n"
        f"CATÁLOGO DE CURSOS DISPONÍVEIS:\n{course_list}\n\n"
        f"Retorne um JSON com a lista de cursos relevantes, ordenados do mais ao menos relevante. "
        f"Para cada curso relevante, inclua o id e um score de 0.0 a 1.0. "
        f"Inclua apenas cursos genuinamente relevantes para o objetivo do aluno. "
        f"Se nenhum for relevante, retorne lista vazia."
    )

    schema = {
        "type": "object",
        "properties": {
            "relevant_courses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "score": {"type": "number"},
                    },
                    "required": ["id", "score"],
                },
            }
        },
        "required": ["relevant_courses"],
    }

    try:
        response = await _client.aio.models.generate_content(
            model=_CHAT_MODEL,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.0,
            ),
        )
        data = _json.loads(response.text or "{}")
        relevant = data.get("relevant_courses", [])

        # Build id→score map
        score_map: dict[str, float] = {
            str(r["id"]): float(r["score"])
            for r in relevant
            if "id" in r and "score" in r
        }

        if not score_map:
            logger.info("_filter_courses_with_gemini: Gemini returned no relevant courses, using all as fallback")
            return [(c, 0.51) for c in courses]

        # Match courses by id and sort by score
        scored: list[tuple[dict, float]] = []
        for course in courses:
            cid = str(course.get("id") or "")
            if cid in score_map:
                scored.append((course, score_map[cid]))

        scored.sort(key=lambda x: x[1], reverse=True)

        for course, score in scored:
            logger.info(
                "  gemini_ranked: title='%s' score=%.2f",
                course.get("title") or course.get("name"), score,
            )

        return scored if scored else [(c, 0.51) for c in courses]

    except Exception as exc:
        logger.warning("_filter_courses_with_gemini: failed — %s", exc)
        return [(c, 0.51) for c in courses]


def _rank_courses(
    courses: list[dict],
    rag_chunks: list[RagChunk],
) -> list[tuple[dict, float]]:
    """Kept for reference — main path now uses _filter_courses_with_gemini."""
    if not courses:
        return []
    if not rag_chunks:
        return [(course, 0.51) for course in courses]
    best_score = max(chunk.similarity for chunk in rag_chunks)
    if best_score < _RELEVANCE_THRESHOLD:
        return []
    return [(course, best_score) for course in courses]


async def _generate_justification(
    item_title: str,
    item_type: PlanItemType,
    gaps: list[Gap],
    goal: str,
    rag_score: float = 0.0,
) -> str:
    """
    Ask Gemini for a 1–2 sentence justification explaining why this item was
    included in the study plan. Falls back to a generic message on error.

    If rag_score is 0 (no direct RAG match), the prompt instructs Gemini to
    be honest about the indirect relevance rather than hallucinating a connection.
    """
    gap_topics = ", ".join(g.topic for g in gaps) if gaps else "tópicos gerais"
    type_label = "Curso CEFIS" if item_type == PlanItemType.CEFIS_COURSE else "Conteúdo Gerado pela IA"

    if rag_score > 0:
        relevance_hint = (
            f"Este curso foi identificado como diretamente relevante para o objetivo do aluno "
            f"com base no conteúdo das aulas indexadas."
        )
    else:
        relevance_hint = (
            f"Este curso foi incluído como complemento ao plano, pois o catálogo disponível "
            f"não contém cursos com correspondência direta ao objetivo. "
            f"Seja honesto sobre essa limitação na justificativa."
        )

    prompt = (
        f"Você é um tutor de estudos. Explique em 1 a 2 frases curtas e diretas "
        f"por que o item '{item_title}' ({type_label}) foi incluído no plano de estudos "
        f"de um aluno cujo objetivo é '{goal}' e que tem lacunas em: {gap_topics}. "
        f"{relevance_hint} "
        f"Seja específico e honesto. Responda apenas com a justificativa, sem introdução."
    )

    try:
        response = await _client.aio.models.generate_content(
            model=_CHAT_MODEL,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(
                temperature=0.5,
            ),
        )
        text = (response.text or "").strip()
        return text if text else _fallback_justification(item_title, gaps)
    except Exception as exc:
        logger.warning("_generate_justification failed for '%s': %s", item_title, exc)
        return _fallback_justification(item_title, gaps)


def _fallback_justification(item_title: str, gaps: list[Gap]) -> str:
    if gaps:
        return (
            f"Este item aborda '{gaps[0].topic}', uma das lacunas identificadas no seu diagnóstico, "
            f"e é essencial para atingir seu objetivo de aprendizado."
        )
    return (
        f"'{item_title}' foi selecionado para complementar seu plano de estudos "
        f"e reforçar os conceitos fundamentais da sua área."
    )

def _estimated_minutes_for_course(course: dict) -> int:
    """
    Extract estimated duration from a CEFIS course dict.
    The CEFIS API always returns duration in seconds — always divide by 60.
    Falls back to 30 minutes if the field is absent or unparseable.
    """
    for key in ("duration", "estimated_duration", "total_duration", "duration_minutes"):
        val = course.get(key)
        if val is not None:
            try:
                seconds = int(val)
                if seconds <= 0:
                    continue
                return max(1, seconds // 60)
            except (TypeError, ValueError):
                pass
    return 30


def _estimated_minutes_for_gap(gap: Gap, time_available: int) -> int:
    """
    Estimate how many minutes a generated-content item should take.
    Critical gaps get a bit more time; regular gaps get a proportional slice.
    """
    if gap.is_critical:
        return min(time_available, 20)
    return min(time_available, 15)


async def build_plan(
    session: "Session",
    courses: list[dict],
    rag_chunks: list[RagChunk],
) -> StudyPlan:
    """
    Assemble a ``StudyPlan`` from CEFIS courses and generated-content items.

    The plan is returned as quickly as possible:
    - CEFIS_COURSE items are placeholders — the actual summaries/apostilas are
      generated on-demand when the user clicks "Gerar Resumo" etc. (task 8).
    - GENERATED_CONTENT items are also placeholders with a title and justification;
      content is generated lazily via POST /content/generate.
    - Justifications for all items are fetched in parallel to minimise latency.

    Algorithm:
    1. Rank courses by RAG relevance (threshold check).
    2. Determine the effective item limit from time_available + critical gaps.
    3. Build item stubs synchronously (no Gemini calls yet).
    4. Fire all justification requests in parallel via asyncio.gather.
    5. Attach justifications and return the StudyPlan.
    """
    profile = session.profile
    if profile is None:
        logger.error("build_plan called with session that has no profile")
        return StudyPlan(items=[], total_estimated_minutes=0)

    diagnosis = session.diagnosis
    gaps: list[Gap] = diagnosis.gaps if diagnosis else []
    goal: str = profile.goal
    time_available: int = profile.time_available

    has_critical_gaps = any(g.is_critical for g in gaps)
    limit = _item_limit(time_available, has_critical_gaps)

    area: str = getattr(profile, "area", "") or ""

    # Log RAG chunks for debugging
    if rag_chunks:
        logger.info(
            "build_plan: %d RAG chunks available for course filtering",
            len(rag_chunks),
        )
        for chunk in rag_chunks:
            logger.info(
                "  RAG chunk: course='%s' lesson='%s' similarity=%.3f",
                chunk.course_name, chunk.lesson_name, chunk.similarity,
            )

    # Use Gemini to filter and rank courses using RAG context + student profile
    ranked_courses = await _filter_courses_with_gemini(courses, rag_chunks, goal, area, gaps)

    logger.info(
        "build_plan: goal='%s' area='%s' time=%d limit=%d total_courses=%d ranked=%d gaps=%d",
        goal, area, time_available, limit, len(courses), len(ranked_courses), len(gaps),
    )


    ItemSpec = tuple[PlanItem, list[Gap], float]  # item, gaps, rag_score
    item_specs: list[ItemSpec] = []
    position = 1

    # CEFIS_COURSE items
    for course, score in ranked_courses:
        if position > limit:
            break
        course_id = str(course.get("id") or course.get("slug") or "")
        title = course.get("title") or course.get("name") or f"Curso {course_id}"
        estimated = _estimated_minutes_for_course(course)

        item = PlanItem(
            id=uuid.uuid4(),
            position=position,
            type=PlanItemType.CEFIS_COURSE,
            title=title,
            estimated_minutes=estimated,
            justification="",
            course_id=course_id if course_id else None,
            course_details=course,
        )
        item_specs.append((item, gaps, score))
        position += 1

    remaining_slots = limit - len(item_specs)
    if remaining_slots > 0:
        content_gaps = gaps if gaps else [Gap(topic=goal, is_critical=False, wrong_count=0)]
        for gap in content_gaps:
            if remaining_slots <= 0:
                break
            title = f"Material de estudo: {gap.topic}"
            estimated = _estimated_minutes_for_gap(gap, time_available)

            item = PlanItem(
                id=uuid.uuid4(),
                position=position,
                type=PlanItemType.GENERATED_CONTENT,
                title=title,
                estimated_minutes=estimated,
                justification="",
            )
            item_specs.append((item, [gap], 0.0))
            position += 1
            remaining_slots -= 1

    justifications: list[str] = await asyncio.gather(
        *[
            _generate_justification(
                item_title=item.title,
                item_type=item.type,
                gaps=item_gaps,
                goal=goal,
                rag_score=rag_score,
            )
            for item, item_gaps, rag_score in item_specs
        ]
    )

    plan_items: list[PlanItem] = []
    for (item, _, __), justification in zip(item_specs, justifications):
        item.justification = justification
        plan_items.append(item)


    def _sort_key(item: PlanItem) -> tuple[int, int]:
        if item.type == PlanItemType.CEFIS_COURSE:
            return (0, item.position)
        for gap in gaps:
            if gap.topic.lower() in item.title.lower():
                return (1, 0 if gap.is_critical else 1)
        return (1, 2)

    plan_items.sort(key=_sort_key)
    for idx, item in enumerate(plan_items, start=1):
        item.position = idx

    total_minutes = sum(i.estimated_minutes for i in plan_items)
    return StudyPlan(items=plan_items, total_estimated_minutes=total_minutes)


async def adjust_plan(
    session: "Session",
    new_time_available: int,
    courses: list[dict],
    rag_chunks: list[RagChunk],
) -> StudyPlan:
    """
    Recalculate the study plan with a new ``time_available`` value.

    Validates that ``new_time_available > 0`` (Req 5.4), updates the session
    profile in-place, then delegates to ``build_plan``.

    Args:
        session:           The current session (profile will be mutated).
        new_time_available: New time budget in minutes; must be > 0.
        courses:           CEFIS course list (same as used in the original plan).
        rag_chunks:        RAG chunks (same as used in the original plan).

    Returns:
        A freshly assembled ``StudyPlan``.

    Raises:
        ValueError: If ``new_time_available`` is not a positive integer.
    """
    if not isinstance(new_time_available, int) or new_time_available < 1:
        raise ValueError(
            "new_time_available must be a positive integer greater than zero."
        )

    if session.profile is not None:
        session.profile = session.profile.model_copy(
            update={"time_available": new_time_available}
        )

    return await build_plan(session, courses, rag_chunks)
