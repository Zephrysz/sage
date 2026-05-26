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
def _rank_courses(
    courses: list[dict],
    rag_chunks: list[RagChunk],
) -> list[tuple[dict, float]]:
    """
    Return courses to include in the plan.

    The RAG chunks are already the result of a semantic search against the
    student's gaps — they represent relevant topics, not specific courses.
    So we don't try to match chunks back to courses by name.

    Instead:
    - If any chunk cleared the threshold (i.e., rag_chunks is non-empty,
      since query_rag already filters by threshold), the topic is relevant
      and all courses are candidates.
    - Courses are returned as-is (preserving the CEFIS API order, which is
      typically by relevance/popularity) paired with the best overall chunk
      similarity as a shared score.
    - If no chunks exist above the threshold, no courses are returned (Req 5.5).
    """
    if not rag_chunks:
        return []

    best_score = max(chunk.similarity for chunk in rag_chunks)
    if best_score < _RELEVANCE_THRESHOLD:
        return []

    return [(course, best_score) for course in courses]


async def _generate_justification(
    item_title: str,
    item_type: PlanItemType,
    gaps: list[Gap],
    goal: str,
) -> str:
    """
    Ask Gemini for a 1–2 sentence justification explaining why this item was
    included in the study plan.  Falls back to a generic message on error.
    """
    gap_topics = ", ".join(g.topic for g in gaps) if gaps else "tópicos gerais"
    type_label = "Curso CEFIS" if item_type == PlanItemType.CEFIS_COURSE else "Conteúdo Gerado pela IA"

    prompt = (
        f"Você é um tutor de estudos. Explique em 1 a 2 frases curtas e diretas "
        f"por que o item '{item_title}' ({type_label}) foi incluído no plano de estudos "
        f"de um aluno cujo objetivo é '{goal}' e que tem lacunas em: {gap_topics}. "
        f"Seja específico e motivador. Responda apenas com a justificativa, sem introdução."
    )

    try:
        response = await _client.aio.models.generate_content(
            model=_CHAT_MODEL,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=256,
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
    Falls back to 30 minutes if the field is absent or unparseable.
    """
    for key in ("duration", "estimated_duration", "duration_minutes", "total_duration"):
        val = course.get(key)
        if val is not None:
            try:
                return max(1, int(val))
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

    ranked_courses = _rank_courses(courses, rag_chunks)


    ItemSpec = tuple[PlanItem, list[Gap]]
    item_specs: list[ItemSpec] = []
    position = 1

    # CEFIS_COURSE items
    for course, _score in ranked_courses:
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
            justification="",          # filled in below
            course_id=course_id if course_id else None,
            course_details=course,
        )
        item_specs.append((item, gaps))
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
            item_specs.append((item, [gap]))
            position += 1
            remaining_slots -= 1

    justifications: list[str] = await asyncio.gather(
        *[
            _generate_justification(
                item_title=item.title,
                item_type=item.type,
                gaps=item_gaps,
                goal=goal,
            )
            for item, item_gaps in item_specs
        ]
    )

    plan_items: list[PlanItem] = []
    for (item, _), justification in zip(item_specs, justifications):
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
