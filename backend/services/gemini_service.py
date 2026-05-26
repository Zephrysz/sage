"""
Gemini service — chat, structured output, and embeddings.

Uses the `google-genai` SDK (google.genai).
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)

_CHAT_MODEL = "gemini-2.5-flash"
_EMBED_MODEL = "gemini-embedding-001"

_PROFILE_FIELD_SCHEMAS: dict[str, dict] = {
    "goal": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "The student's professional goal or area of study interest.",
            }
        },
        "required": ["goal"],
    },
    "level": {
        "type": "object",
        "properties": {
            "level": {
                "type": "string",
                "enum": ["iniciante", "intermediario", "avancado"],
                "description": "Experience level: iniciante, intermediario, or avancado.",
            }
        },
        "required": ["level"],
    },
    "time_available": {
        "type": "object",
        "properties": {
            "time_available": {
                "type": "integer",
                "description": "Minutes available per study session (positive integer).",
            }
        },
        "required": ["time_available"],
    },
    "learning_style": {
        "type": "object",
        "properties": {
            "learning_style": {
                "type": "string",
                "enum": ["video", "leitura", "audio"],
                "description": "Preferred learning style: video, leitura, or audio.",
            }
        },
        "required": ["learning_style"],
    },
}

async def extract_profile_field(
    history: list[dict],
    field_name: str,
    user_message: str,
) -> str | int | None:
    """
    Try to extract a single profile field value from the user's message.

    Uses structured output (JSON schema) so the model returns a typed value
    or nothing when the message doesn't contain the expected information.

    Args:
        history: List of previous chat messages as dicts with 'role' and 'content'.
        field_name: One of 'goal', 'level', 'time_available', 'learning_style'.
        user_message: The latest message from the user.

    Returns:
        The extracted value (str or int) or None if extraction failed.
    """
    schema = _PROFILE_FIELD_SCHEMAS.get(field_name)
    if schema is None:
        logger.warning("Unknown profile field: %s", field_name)
        return None

    system_prompt = (
        "You are a data extraction assistant. "
        "Extract the requested profile field from the user's message. "
        "If the message does not clearly provide the value, return null for the field. "
        "Respond only with valid JSON matching the provided schema."
    )

    # Build contents list: system + history + current user message
    contents = _build_contents(history, user_message)

    try:
        response = await _client.aio.models.generate_content(
            model=_CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.0,
            ),
        )
        raw = response.text or ""
        parsed = json.loads(raw)
        value = parsed.get(field_name)
        if value is None or value == "":
            return None
        if field_name == "time_available":
            try:
                value = int(value)
                return value if value > 0 else None
            except (TypeError, ValueError):
                return None
        return value
    except Exception as exc:
        logger.error("extract_profile_field(%s) failed: %s", field_name, exc)
        return None


async def chat_turn(
    history: list[dict],
    system_prompt: str,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Perform a single chat turn and stream the response as text chunks.

    Args:
        history: List of previous messages as dicts with 'role' and 'content'.
                 Only the most recent min(len, 10) messages are sent to Gemini.
        system_prompt: The system instruction for this turn.
        user_message: The latest user message.

    Yields:
        Text chunks from the model response.
    """
    contents = _build_contents(history, user_message)

    try:
        async for chunk in await _client.aio.models.generate_content_stream(
            model=_CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
            ),
        ):
            text = chunk.text
            if text:
                yield text
    except Exception as exc:
        logger.error("chat_turn failed: %s", exc)
        yield "Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente."


async def embed(text: str) -> list[float]:
    """
    Generate a 768-dimensional embedding for the given text.

    Uses the `gemini-embedding-001` model.

    Args:
        text: The text to embed.

    Returns:
        A list of 768 floats.

    Raises:
        RuntimeError: If the embedding call fails.
    """
    try:
        response = await _client.aio.models.embed_content(
            model=_EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768),
        )
        return response.embeddings[0].values
    except Exception as exc:
        logger.error("embed() failed: %s", exc)
        raise RuntimeError(f"Embedding failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_contents(history: list[dict], user_message: str) -> list[dict]:
    """
    Build the contents list for the Gemini API.

    Keeps only the most recent min(len(history), 10) messages, then appends
    the current user message.
    """
    recent = history[-10:] if len(history) > 10 else history
    contents = [
        {"role": msg["role"], "parts": [{"text": msg["content"]}]}
        for msg in recent
    ]
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents
