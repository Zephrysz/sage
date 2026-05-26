"""
Chat router — POST /chat/message

Handles the full onboarding state machine and streams responses via SSE.

States handled here:
  ONBOARDING          → collect 4 profile fields one at a time
  AWAITING_CONFIRMATION → confirm or correct the collected profile
  STUDY_MODE          → contextual RAG chat (stub, implemented in task 9)
"""

from __future__ import annotations

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
from services import gemini_service
from session_store import get_session, update_session

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessageRequest(BaseModel):
    message: str

_PROFILE_FIELDS_ORDER = ["goal", "level", "time_available", "learning_style"]

_FIELD_QUESTIONS = {
    "goal": (
        "Qual é o seu objetivo profissional ou área de interesse que você quer desenvolver? "
        "Por exemplo: 'quero me tornar analista de dados' ou 'preciso aprender sobre finanças pessoais'."
    ),
    "level": (
        "Qual é o seu nível de experiência nessa área? "
        "Você se considera iniciante, intermediário ou avançado?"
    ),
    "time_available": (
        "Quantos minutos por dia você tem disponível para estudar? "
        "Por exemplo: 15, 30, 60 minutos."
    ),
    "learning_style": (
        "Qual é o seu estilo de aprendizagem preferido? "
        "Você prefere aprender por vídeo, leitura ou áudio?"
    ),
}

_FIELD_LABELS = {
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
}


_ONBOARDING_SYSTEM = (
    "Você é o Tutor CEFIS, um assistente de aprendizado personalizado. "
    "Seu tom é amigável, encorajador e direto. "
    "Você está coletando informações do aluno para montar um plano de estudos personalizado. "
    "Faça apenas uma pergunta por vez. Seja conciso e natural."
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
        escaped = chunk.replace("\n", "\\n")
        yield f"data: {escaped}\n\n"
    yield "data: [DONE]\n\n"


async def _sse_static(text: str):
    """Yield a single static text as SSE."""
    escaped = text.replace("\n", "\\n")
    yield f"data: {escaped}\n\n"
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
        # Stub for now 
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
                f"[SYSTEM: Field '{current_field}' was just collected. Now ask about '{next_field}': {question}]",
            ):
                yield chunk
    else:
        _persist_chat(session_id, history_with_user)
        rephrased_prompt = (
            f"[SYSTEM: The user's response did not clearly answer the question about '{current_field}'. "
            f"Rephrase the question with a concrete example to help them understand what you need. "
            f"Original question: {_FIELD_QUESTIONS[current_field]}]"
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
            "[SYSTEM: The user confirmed their profile. Respond enthusiastically and say you will now start the knowledge diagnosis.]",
        ):
            yield chunk

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
    Stub for STUDY_MODE
    """
    _persist_chat(session_id, history_with_user)
    system = (
        "Você é o Tutor CEFIS no modo de estudo. "
        "Responda dúvidas sobre o conteúdo educacional do curso que o aluno está estudando. "
        "Se a pergunta não for sobre conteúdo educacional, redirecione gentilmente."
    )
    async for chunk in gemini_service.chat_turn(history, system, user_message):
        yield chunk


def _next_missing_field(profile_data: dict) -> str | None:
    """Return the next field in order that hasn't been collected yet."""
    for field in _PROFILE_FIELDS_ORDER:
        if field not in profile_data or profile_data[field] is None:
            return field
    return None


def _format_profile_summary(profile_data: dict) -> str:
    level_label = _LEVEL_LABELS.get(str(profile_data.get("level", "")), profile_data.get("level", ""))
    style_label = _STYLE_LABELS.get(str(profile_data.get("learning_style", "")), profile_data.get("learning_style", ""))
    time_val = profile_data.get("time_available", "")
    return (
        f"• Objetivo: {profile_data.get('goal', '')}\n"
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
