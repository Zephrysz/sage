"""
Gemini service — chat, structured output, and embeddings.

"""

from __future__ import annotations

import json
import logging
import uuid
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

    #system + history + current user message
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


# MCQ generation for diagnosis

_MCQ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The question text.",
                    },
                    "options": {
                        "type": "object",
                        "properties": {
                            "A": {"type": "string"},
                            "B": {"type": "string"},
                            "C": {"type": "string"},
                            "D": {"type": "string"},
                            "E": {"type": "string"},
                        },
                        "required": ["A", "B", "C", "D", "E"],
                    },
                    "correct_answer": {
                        "type": "string",
                        "enum": ["A", "B", "C", "D", "E"],
                        "description": "The letter of the correct answer.",
                    },
                    "topic": {
                        "type": "string",
                        "description": "The topic or skill area this question tests.",
                    },
                },
                "required": ["text", "options", "correct_answer", "topic"],
            },
        }
    },
    "required": ["questions"],
}


async def generate_mcq_questions(
    goal: str,
    level: str,
    n: int = 5,
) -> list:
    """
    Generate multiple-choice questions for the diagnosis phase.

    Uses Gemini structured output to produce exactly `n` questions (3–5)
    tailored to the student's goal and experience level. Each question has
    5 options (A–E).

    Args:
        goal: The student's professional goal or area of interest.
        level: Experience level string ('iniciante', 'intermediario', 'avancado').
        n: Number of questions to generate (default 5, clamped to 3–5).

    Returns:
        A list of DiagnosisQuestion objects.
        Returns an empty list on any Gemini error (fallback: classify as Iniciante).
    """
    from models.diagnosis import DiagnosisQuestion, DiagnosisOptions

    n = max(3, min(5, n))

    level_labels = {
        "iniciante": "beginner",
        "intermediario": "intermediate",
        "avancado": "advanced",
    }
    level_en = level_labels.get(level, level)

    system_prompt = (
        "You are an expert educational assessment designer. "
        "Generate multiple-choice questions to diagnose a student's knowledge gaps. "
        "Each question must have exactly 5 options (A, B, C, D, E) with only one correct answer. "
        "Questions should be clear, unambiguous, and appropriate for the student's level. "
        "Cover different topics/skills relevant to the student's goal. "
        "Respond only with valid JSON matching the provided schema."
    )

    user_prompt = (
        f"Generate exactly {n} multiple-choice questions to diagnose knowledge gaps for a student with:\n"
        f"- Professional goal: {goal}\n"
        f"- Experience level: {level_en}\n\n"
        f"Each question should test a different topic relevant to '{goal}'. "
        f"Make questions practical and scenario-based when possible. "
        f"Each question must have exactly 5 answer options (A, B, C, D, E)."
    )

    try:
        response = await _client.aio.models.generate_content(
            model=_CHAT_MODEL,
            contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=_MCQ_SCHEMA,
                temperature=0.7,
            ),
        )
        raw = response.text or ""
        parsed = json.loads(raw)
        raw_questions = parsed.get("questions", [])

        if not raw_questions:
            logger.warning("generate_mcq_questions: Gemini returned empty questions list")
            return []

        questions = []
        for q in raw_questions:
            opts = q.get("options", {})
            try:
                question = DiagnosisQuestion(
                    id=uuid.uuid4(),
                    text=q["text"],
                    options=DiagnosisOptions(
                        A=opts.get("A", ""),
                        B=opts.get("B", ""),
                        C=opts.get("C", ""),
                        D=opts.get("D", ""),
                        E=opts.get("E", ""),
                    ),
                    correct_answer=q["correct_answer"],
                    topic=q["topic"],
                )
                questions.append(question)
            except Exception as exc:
                logger.warning("Skipping malformed question: %s — %s", q, exc)

        return questions

    except Exception as exc:
        logger.error("generate_mcq_questions failed: %s", exc)
        return []
