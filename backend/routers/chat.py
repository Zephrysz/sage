"""
Chat router — POST /chat/message

Handles the full onboarding state machine and streams responses via SSE.

States handled here:
  ONBOARDING          → collect 4 profile fields one at a time
  AWAITING_CONFIRMATION → confirm or correct the collected profile
  STUDY_MODE          → contextual RAG chat with course-scoped retrieval
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.session import (
    ExperienceLevel,
    LearningStyle,
    Profile,
    SessionState,
)
from services import gemini_service, rag_service
from session_store import get_session, update_session, delete_session

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessageRequest(BaseModel):
    message: str

_PROFILE_FIELDS_ORDER = ["area", "goal", "level", "time_available", "learning_style"]

_FIELD_QUESTIONS = {
    "area": (
        "Em qual área você quer se desenvolver? "
        "Seja específico para que o plano seja mais preciso."
    ),
    "goal": (
        "Qual é o seu objetivo profissional nessa área? "
        "O que você quer alcançar?"
    ),
    "level": (
        "Qual é o seu nível de experiência nessa área? "
        "Você se considera iniciante, intermediário ou avançado?"
    ),
    "time_available": (
        "Quantos minutos por sessão de estudo você tem disponível? "
        "Por exemplo: 15, 30, 45, 60 minutos."
    ),
    "learning_style": (
        "Qual é o seu estilo de aprendizagem preferido? "
        "Você prefere aprender por vídeo, leitura, áudio ou de forma cinestésica (prática, exercícios, fazer)?"
    ),
}

_FIELD_LABELS = {
    "area": "Área de interesse",
    "goal": "Objetivo profissional",
    "level": "Nível de experiência",
    "time_available": "Tempo disponível por sessão",
    "learning_style": "Estilo de aprendizagem",
}

_LEVEL_LABELS = {
    "iniciante": "Iniciante",
    "intermediario": "Intermediário",
    "avancado": "Avançado",
}

_STYLE_LABELS = {
    "video": "Vídeo",
    "leitura": "Leitura",
    "audio": "Áudio",
    "cinestetico": "Cinestésico",
}


_ONBOARDING_SYSTEM = (
    "Você é o Tutor CEFIS, um assistente de aprendizado personalizado. "
    "Seu tom é amigável, encorajador e direto. "
    "Você está coletando exatamente 5 informações do aluno para montar um plano de estudos. "
    "REGRA CRÍTICA: Faça APENAS a pergunta indicada pelo sistema. "
    "NÃO faça perguntas adicionais, NÃO peça esclarecimentos além do campo atual, "
    "NÃO improvise perguntas fora das 5 definidas. "
    "Seja conciso: uma frase de transição + a pergunta do campo atual."
)

_CONFIRMATION_SYSTEM = (
    "Você é o Tutor CEFIS. "
    "Você acabou de coletar o perfil do aluno e está aguardando confirmação. "
    "Se o aluno confirmar, responda de forma entusiasmada que vai iniciar o diagnóstico. "
    "Se o aluno quiser corrigir algo, pergunte qual campo deseja corrigir e colete o novo valor. "
    "Seja conciso e natural."
)



async def _sse_stream(text_gen):
    """Wrap an async generator of text chunks into SSE format."""
    async for chunk in text_gen:
        # Encode each line as a separate SSE data line to preserve newlines
        for line in chunk.split("\n"):
            yield f"data: {line}\n"
        yield "\n"
    yield "data: [DONE]\n\n"


async def _sse_static(text: str):
    """Yield a single static text as SSE."""
    for line in text.split("\n"):
        yield f"data: {line}\n"
    yield "\n"
    yield "data: [DONE]\n\n"


@router.post("/message")
async def chat_message(
    body: ChatMessageRequest,
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> StreamingResponse:
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    state = SessionState(session["state"])
    history: list[dict] = session.get("chat_history", [])
    user_message = body.message.strip()

    history_with_user = history + [
        {"role": "user", "content": user_message, "timestamp": datetime.utcnow().isoformat()}
    ]

    if state == SessionState.ONBOARDING:
        response_gen = _handle_onboarding(
            session, x_session_id, history, user_message, history_with_user
        )
    elif state == SessionState.AWAITING_CONFIRMATION:
        response_gen = _handle_awaiting_confirmation(
            session, x_session_id, history, user_message, history_with_user
        )
    elif state == SessionState.STUDY_MODE:
        response_gen = _handle_study_mode(
            session, x_session_id, history, user_message, history_with_user
        )
    else:
        async def _not_available():
            yield "O chat não está disponível neste momento."

        response_gen = _not_available()

    return StreamingResponse(
        _sse_stream(response_gen),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

async def _handle_onboarding(
    session: dict,
    session_id: str,
    history: list[dict],
    user_message: str,
    history_with_user: list[dict],
):
    """
    Collect profile fields one at a time.

    Determines which field is currently being collected, tries to extract it
    from the user's message, and either advances to the next field or asks
    again with a rephrased question.
    """
    profile_data: dict = session.get("profile_data") or {}

    current_field = _next_missing_field(profile_data)

    if current_field is None: #abnormal
        _transition_to_awaiting_confirmation(session_id, profile_data, history_with_user)
        async for chunk in _stream_confirmation_summary(profile_data, history):
            yield chunk
        return

    extracted = await gemini_service.extract_profile_field(
        history, current_field, user_message
    )

    if extracted is not None:
        profile_data[current_field] = extracted
        next_field = _next_missing_field(profile_data)

        if next_field is None:
            _transition_to_awaiting_confirmation(session_id, profile_data, history_with_user)
            async for chunk in _stream_confirmation_summary(profile_data, history):
                yield chunk
        else:
            _persist_chat(session_id, history_with_user, extra={"profile_data": profile_data})
            question = _FIELD_QUESTIONS[next_field]
            async for chunk in gemini_service.chat_turn(
                history_with_user,
                _ONBOARDING_SYSTEM,
                f"[SYSTEM: Field '{current_field}' collected successfully. Now ask ONLY about '{next_field}'. "
                f"Base question: {question}. "
                f"If the next field is 'goal', generate 2-3 short examples relevant to the area the user just mentioned — do NOT use generic or unrelated examples. "
                f"Do NOT ask anything else.]",
            ):
                yield chunk
    else:
        _persist_chat(session_id, history_with_user)
        if current_field == "area":
            rephrased_prompt = (
                "[SYSTEM: The user's response was too vague — no specific subject area was identified. "
                "Ask them to be more specific. Give 2-3 examples that feel relevant to what they mentioned "
                "(e.g. if they mentioned work/career, suggest contabilidade, fiscal, trabalhista, gestão; "
                "if they mentioned technology, suggest tecnologia, sistemas, automação fiscal). "
                "Keep it conversational, one sentence.]"
            )
        elif current_field == "goal":
            rephrased_prompt = (
                "[SYSTEM: The user's response described a career aspiration but didn't mention "
                "a specific professional goal. "
                "Acknowledge their answer warmly, then ask: "
                "'E qual é o seu objetivo profissional nessa área? "
                "Por exemplo: ser promovido, passar em uma certificação, mudar de carreira...']"
            )
        else:
            rephrased_prompt = (
                f"[SYSTEM: The user's response did not clearly answer the question about '{current_field}'. "
                f"Rephrase the question with a concrete example to help them understand what you need. "
                f"Original question: {_FIELD_QUESTIONS[current_field]}. Do NOT ask anything else.]"
            )
        async for chunk in gemini_service.chat_turn(
            history_with_user,
            _ONBOARDING_SYSTEM,
            rephrased_prompt,
        ):
            yield chunk


async def _handle_awaiting_confirmation(
    session: dict,
    session_id: str,
    history: list[dict],
    user_message: str,
    history_with_user: list[dict],
):
    """
    Detect confirmation or correction request.

    If confirmed → store Profile and transition to DIAGNOSIS.
    If correction → collect the specific field and return to AWAITING_CONFIRMATION.
    """
    profile_data: dict = session.get("profile_data") or {}

    # Use Gemini to classify the intent
    intent_schema = {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["confirm", "correct", "unclear"],
            },
            "field_to_correct": {
                "type": "string",
                "enum": ["goal", "level", "time_available", "learning_style", "none"],
            },
        },
        "required": ["intent", "field_to_correct"],
    }

    from google.genai import types as gtypes

    try:
        intent_response = await gemini_service._client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[{"role": "user", "parts": [{"text": user_message}]}],
            config=gtypes.GenerateContentConfig(
                system_instruction=(
                    "Classify the user's intent regarding their profile confirmation. "
                    "If they are confirming/agreeing, return intent='confirm'. "
                    "If they want to correct a specific field, return intent='correct' and the field name. "
                    "If unclear, return intent='unclear'. "
                    "Field names: goal, level, time_available, learning_style."
                ),
                response_mime_type="application/json",
                response_schema=intent_schema,
                temperature=0.0,
            ),
        )
        import json as _json
        intent_data = _json.loads(intent_response.text or "{}")
        intent = intent_data.get("intent", "unclear")
        field_to_correct = intent_data.get("field_to_correct", "none")
    except Exception as exc:
        logger.error("Intent classification failed: %s", exc)
        intent = "unclear"
        field_to_correct = "none"

    if intent == "confirm":
        try:
            profile = Profile(
                area=profile_data["area"],
                goal=profile_data["goal"],
                level=ExperienceLevel(profile_data["level"]),
                time_available=int(profile_data["time_available"]),
                learning_style=LearningStyle(profile_data["learning_style"]),
            )
        except Exception as exc:
            logger.error("Profile construction failed: %s", exc)
            yield "Houve um problema ao salvar seu perfil. Vamos tentar novamente."
            return

        update_session(
            session_id,
            {
                "profile": profile.model_dump(mode="json"),
                "state": SessionState.DIAGNOSIS.value,
                "chat_history": _trim_history(history_with_user),
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        async for chunk in gemini_service.chat_turn(
            history_with_user,
            _CONFIRMATION_SYSTEM,
            "[SYSTEM: The user confirmed their profile. Respond in 2-3 sentences: "
            "first, confirm enthusiastically that the profile is saved; "
            "then warn that a quick knowledge quiz (5 multiple-choice questions) is about to start "
            "to identify their knowledge gaps and personalize the study plan. "
            "Be warm and encouraging. Be brief.]",
        ):
            yield chunk

        # Small delay so the user can read the message before the diagnosis UI appears
        import asyncio as _asyncio
        await _asyncio.sleep(5)

        # Signal state change to frontend
        yield json.dumps({"state": SessionState.DIAGNOSIS.value})

    elif intent == "correct" and field_to_correct not in ("none", ""):
        _persist_chat(session_id, history_with_user)
        question = _FIELD_QUESTIONS.get(field_to_correct, "Qual valor você gostaria de corrigir?")
        correction_prompt = (
            f"[SYSTEM: The user wants to correct the field '{field_to_correct}'. "
            f"Ask them for the new value. Question: {question}]"
        )

        update_session(session_id, {"correcting_field": field_to_correct})
        async for chunk in gemini_service.chat_turn(
            history_with_user,
            _CONFIRMATION_SYSTEM,
            correction_prompt,
        ):
            yield chunk

    else:
        _persist_chat(session_id, history_with_user)
        summary = _format_profile_summary(profile_data)
        reprompt = (
            f"[SYSTEM: The user's response was unclear. Re-show the profile summary and ask for confirmation or correction. "
            f"Profile: {summary}]"
        )
        async for chunk in gemini_service.chat_turn(
            history_with_user,
            _CONFIRMATION_SYSTEM,
            reprompt,
        ):
            yield chunk


async def _handle_study_mode(
    session: dict,
    session_id: str,
    history: list[dict],
    user_message: str,
    history_with_user: list[dict],
):
    """
    STUDY_MODE: contextual RAG chat.

    Flow:
    1. Classify the question via Gemini (educational vs. navigation/out-of-scope).
    2. Educational → retrieve RAG chunks (course-scoped + global complement),
       build a context-rich system prompt, stream Gemini answer, append source refs.
    3. Out-of-scope → redirect to study plan topic.
    4. Both RAG and Gemini fail → stream service_unavailable event and terminate session.
    5. Only one fails → stream a soft error message.
    """
    current_course_id: str | None = session.get("current_course_id")
    study_plan = session.get("study_plan") or {}
    plan_items = study_plan.get("items", []) if isinstance(study_plan, dict) else []
    plan_topic = plan_items[0].get("title", "seu plano de estudos") if plan_items else "seu plano de estudos"

    question_type = await _classify_study_question(user_message)

    if question_type == "navigation":
        _persist_chat(session_id, history_with_user)
        redirect_msg = (
            f"Posso ajudar com dúvidas sobre os tópicos do seu plano de estudos. "
            f"Tem alguma dúvida sobre {plan_topic}?"
        )
        yield redirect_msg
        return

    rag_error: Exception | None = None
    chunks: list = []

    try:
        # Primary: course-scoped query
        if current_course_id:
            chunks = await rag_service.query_rag(
                query_text=user_message,
                course_id=current_course_id,
                top_k=5,
                threshold=0.70,
            )

        # Complement with global index if fewer than 5 chunks
        if len(chunks) < 5:
            remaining = 5 - len(chunks)
            global_chunks = await rag_service.query_rag(
                query_text=user_message,
                course_id=None,
                top_k=remaining,
                threshold=0.70,
            )
            # Avoid duplicates (by content)
            existing_contents = {c.content for c in chunks}
            for gc in global_chunks:
                if gc.content not in existing_contents:
                    chunks.append(gc)
                    existing_contents.add(gc.content)
                    if len(chunks) >= 5:
                        break
    except Exception as exc:
        logger.error("_handle_study_mode: RAG retrieval failed — %s", exc)
        rag_error = exc

    # ── Step 3: build system prompt with RAG context ──────────────────────────
    if chunks:
        context_blocks = "\n\n".join(
            f"[Trecho {i + 1}]\n{c.content}" for i, c in enumerate(chunks)
        )
        system_prompt = (
            "Você é o Tutor CEFIS no modo de estudo. "
            "Responda a dúvida do aluno com base nos trechos de transcrição abaixo. "
            "Seja claro, didático e objetivo. Responda em formato de texto corrido — "
            "NUNCA gere roteiros de áudio, podcasts ou scripts. "
            "Se os trechos não forem suficientes, complemente com seu conhecimento geral.\n\n"
            f"Trechos relevantes:\n{context_blocks}"
        )
    else:
        system_prompt = (
            "Você é o Tutor CEFIS no modo de estudo. "
            "Responda a dúvida do aluno de forma clara e didática em texto corrido. "
            "NUNCA gere roteiros de áudio, podcasts ou scripts. "
            "Use seu conhecimento geral sobre o tema."
        )

    # ── Step 4: generate answer via Gemini ───────────────────────────────────
    gemini_error: Exception | None = None
    full_response_parts: list[str] = []

    try:
        _persist_chat(session_id, history_with_user)
        async for chunk in gemini_service.chat_turn(history_with_user, system_prompt, user_message):
            full_response_parts.append(chunk)
            yield chunk
    except Exception as exc:
        logger.error("_handle_study_mode: Gemini chat_turn failed — %s", exc)
        gemini_error = exc

    # ── Step 5: error handling ────────────────────────────────────────────────
    if gemini_error is not None:
        if rag_error is not None:
            # Both failed → service unavailable, terminate session
            logger.error(
                "_handle_study_mode: both RAG and Gemini failed — terminating session %s",
                session_id,
            )
            yield json.dumps({"service_unavailable": True})
            delete_session(session_id)
        else:
            # Only Gemini failed
            yield "Não foi possível processar sua dúvida no momento. Tente novamente."
        return

    if rag_error is not None and gemini_error is None:
        # Only RAG failed — Gemini answered without context, that's acceptable
        # (already streamed above); just log it
        logger.warning(
            "_handle_study_mode: RAG failed but Gemini answered without context — session %s",
            session_id,
        )

    # ── Step 6: append source references ─────────────────────────────────────
    if chunks and full_response_parts:
        sources = _build_source_references(chunks)
        if sources:
            yield f"\n\n{sources}"


async def _classify_study_question(user_message: str) -> str:
    """
    Use Gemini to classify a student question as 'educational' or 'navigation'.

    Returns 'educational' for content/subject-matter questions and
    'navigation' for requests about changing the plan, navigating the app,
    or anything unrelated to educational content.

    Defaults to 'educational' on any classification error.
    """
    classification_schema = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["educational", "navigation"],
            }
        },
        "required": ["type"],
    }

    from google.genai import types as gtypes

    try:
        response = await gemini_service._client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[{"role": "user", "parts": [{"text": user_message}]}],
            config=gtypes.GenerateContentConfig(
                system_instruction=(
                    "Classify the student's message as either 'educational' or 'navigation'.\n"
                    "'educational': questions about course content, concepts, topics, explanations, "
                    "examples, or any subject-matter doubt.\n"
                    "'navigation': requests to change the study plan, go back, navigate the app, "
                    "adjust time, or anything unrelated to educational content.\n"
                    "When in doubt, classify as 'educational'."
                ),
                response_mime_type="application/json",
                response_schema=classification_schema,
                temperature=0.0,
            ),
        )
        import json as _json
        data = _json.loads(response.text or "{}")
        return data.get("type", "educational")
    except Exception as exc:
        logger.error("_classify_study_question failed: %s", exc)
        return "educational"


def _build_source_references(chunks: list) -> str:
    """
    Build formatted source reference strings from RAG chunks.

    Format: "Fonte: [Nome do Curso] — [Nome da Aula] [lesson_id:<id>]"
    The lesson_id tag is parsed by the frontend to resolve the lesson URL.
    Deduplicates by (course_name, lesson_name) pair.
    """
    seen: set[tuple[str, str]] = set()
    refs: list[str] = []

    for chunk in chunks:
        course_name = getattr(chunk, "course_name", "") or ""
        lesson_name = getattr(chunk, "lesson_name", "") or ""
        lesson_id = getattr(chunk, "lesson_id", "") or ""

        if not course_name or not lesson_name:
            continue

        key = (course_name, lesson_name)
        if key in seen:
            continue
        seen.add(key)

        ref = f"Fonte: {course_name} — {lesson_name}"
        if lesson_id:
            ref += f" [lesson_id:{lesson_id}]"
        refs.append(ref)

    if not refs:
        return ""

    return "\n".join(refs)


def _next_missing_field(profile_data: dict) -> str | None:
    """Return the next field in order that hasn't been collected yet (None counts as missing)."""
    for field in _PROFILE_FIELDS_ORDER:
        val = profile_data.get(field)
        if val is None or val == "" or (isinstance(val, str) and val.strip() == ""):
            return field
    return None


def _format_profile_summary(profile_data: dict) -> str:
    level_label = _LEVEL_LABELS.get(str(profile_data.get("level", "")), profile_data.get("level", "—"))
    style_label = _STYLE_LABELS.get(str(profile_data.get("learning_style", "")), profile_data.get("learning_style", "—"))
    time_val = profile_data.get("time_available", "—")
    area_val = profile_data.get("area") or "—"
    goal_val = profile_data.get("goal") or "—"
    return (
        f"• Área de interesse: {area_val}\n"
        f"• Objetivo profissional: {goal_val}\n"
        f"• Nível: {level_label}\n"
        f"• Tempo disponível: {time_val} minutos por sessão\n"
        f"• Estilo de aprendizagem: {style_label}"
    )


async def _stream_confirmation_summary(profile_data: dict, history: list[dict]):
    """Stream the profile summary and ask for confirmation."""
    summary = _format_profile_summary(profile_data)
    prompt = (
        f"[SYSTEM: All 4 profile fields have been collected. "
        f"Present the following profile summary to the user and ask them to confirm or correct it:\n{summary}]"
    )
    async for chunk in gemini_service.chat_turn(history, _ONBOARDING_SYSTEM, prompt):
        yield chunk


def _transition_to_awaiting_confirmation(
    session_id: str,
    profile_data: dict,
    history: list[dict],
):
    update_session(
        session_id,
        {
            "profile_data": profile_data,
            "state": SessionState.AWAITING_CONFIRMATION.value,
            "chat_history": _trim_history(history),
            "updated_at": datetime.utcnow().isoformat(),
        },
    )


def _persist_chat(session_id: str, history: list[dict], extra: dict | None = None):
    data = {
        "chat_history": _trim_history(history),
        "updated_at": datetime.utcnow().isoformat(),
    }
    if extra:
        data.update(extra)
    update_session(session_id, data)


def _trim_history(history: list[dict]) -> list[dict]:
    """Keep only the most recent 10 messages."""
    return history[-10:] if len(history) > 10 else history
