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
    "area": {
        "type": "object",
        "properties": {
            "area": {
                "type": "string",
                "description": (
                    "The specific subject area or domain the student wants to study. "
                    "Must be a concrete topic related to accounting, tax, labor law, corporate education, "
                    "or similar professional fields. "
                    "Examples: 'contabilidade', 'fiscal/tributário', 'trabalhista', 'eSocial', 'SPED', "
                    "'planejamento tributário', 'gestão empresarial', 'desenvolvimento pessoal', 'tecnologia'. "
                    "If the message is too vague (e.g. 'quero aprender', 'crescer profissionalmente') "
                    "without naming a specific domain, return null."
                ),
            }
        },
        "required": ["area"],
    },
    "goal": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": (
                    "The student's professional goal or career aspiration. "
                    "Accept any career-related aspiration, vague or specific "
                    "(e.g. 'ser promovido', 'passar no exame do CRC', 'dominar o eSocial', "
                    "'abrir escritório contábil', 'liderar equipe'). "
                    "Return null only if the message contains no career or professional intent."
                ),
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
                "description": (
                    "Minutes available per study session. "
                    "Extract the number directly (e.g. '30 minutos' = 30, '1 hora' = 60, '45 min' = 45). "
                    "Must be a positive integer."
                ),
            }
        },
        "required": ["time_available"],
    },
    "learning_style": {
        "type": "object",
        "properties": {
            "learning_style": {
                "type": "string",
                "enum": ["video", "leitura", "audio", "cinestetico"],
                "description": "Preferred learning style: video, leitura, audio, or cinestetico (hands-on/practice).",
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
        "Você é um assistente de extração de dados. "
        "Extraia o campo de perfil solicitado da mensagem do usuário. "
        "Se a mensagem não fornecer claramente o valor, retorne null para o campo. "
        "Responda apenas com JSON válido seguindo o schema fornecido."
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
        if value is None or value == "" or value == "null":
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
    area: str = "",
    n: int = 5,
) -> list:
    """
    Generate multiple-choice questions for the diagnosis phase.

    Uses Gemini structured output to produce exactly `n` questions (3–5)
    tailored to the student's area, goal and experience level.
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
        "Você é um especialista em avaliação educacional. "
        "Gere questões de múltipla escolha em português brasileiro para diagnosticar lacunas de conhecimento do aluno. "
        "Cada questão deve ter exatamente 5 opções (A, B, C, D, E) com apenas uma resposta correta. "
        "As questões devem ser claras, sem ambiguidade e adequadas ao nível do aluno. "
        "Cubra diferentes tópicos relevantes para a área e objetivo do aluno. "
        "Responda apenas com JSON válido seguindo o schema fornecido."
    )

    area_context = f"- Área/domínio específico: {area}\n" if area else ""
    user_prompt = (
        f"Gere exatamente {n} questões de múltipla escolha em português brasileiro "
        f"para diagnosticar lacunas de conhecimento de um aluno com:\n"
        f"{area_context}"
        f"- Objetivo profissional: {goal}\n"
        f"- Nível de experiência: {level}\n\n"
        f"Cada questão deve testar um tópico diferente relevante para '{area or goal}'. "
        f"Prefira questões práticas e baseadas em cenários reais quando possível. "
        f"Cada questão deve ter exatamente 5 opções de resposta (A, B, C, D, E)."
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


# ── TTS voices available via Gemini 2.5 Flash TTS ────────────────────────────

TTS_VOICES = [
    {"name": "Achernar", "description": "Warm, welcoming"},
    {"name": "Aoede",    "description": "Smooth, storytelling"},
    {"name": "Charon",   "description": "Deep, authoritative"},
    {"name": "Fenrir",   "description": "Energetic, dynamic"},
    {"name": "Kore",     "description": "Clear, professional"},
    {"name": "Leda",     "description": "Gentle, calm"},
    {"name": "Orus",     "description": "Confident, direct"},
    {"name": "Puck",     "description": "Playful, expressive"},
    {"name": "Zephyr",   "description": "Breezy, conversational"},
]

_TTS_MODEL = "gemini-2.5-flash-preview-tts"
_TTS_REST_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Wrap raw PCM bytes in a WAV container so browsers can play it."""
    import struct
    data_size = len(pcm_bytes)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,           # chunk size
        1,            # PCM format
        channels,
        sample_rate,
        sample_rate * channels * sample_width,  # byte rate
        channels * sample_width,                # block align
        sample_width * 8,                       # bits per sample
        b'data',
        data_size,
    )
    return header + pcm_bytes


async def synthesize_speech(
    text: str,
    voice_name: str = "Achernar",
    language_code: str = "pt-BR",
    speaking_rate: float = 1.0,
    pitch: float = 0.0,
) -> tuple[bytes, str]:
    """
    Synthesize speech using Gemini 2.5 Flash Preview TTS via the Gemini REST API.

    Uses the existing GEMINI_API_KEY — no separate Cloud TTS key required.
    Returns (audio_bytes, mime_type). Audio is WAV if the API returns PCM,
    or the raw bytes with the reported mime type otherwise.
    """
    import base64
    import httpx
    from config import settings

    api_key = settings.gemini_api_key

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"Say: {text}"}],
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{_TTS_REST_URL}?key={api_key}",
                json=payload,
            )
            if not resp.is_success:
                body_text = resp.text[:500]
                logger.error("TTS API error %d: %s", resp.status_code, body_text)
                raise RuntimeError(f"TTS API returned {resp.status_code}: {body_text}")

            data = resp.json()
            try:
                part = data["candidates"][0]["content"]["parts"][0]["inlineData"]
                audio_b64: str = part["data"]
                mime_type: str = part.get("mimeType", "audio/wav")
            except (KeyError, IndexError) as exc:
                raise RuntimeError(f"Unexpected TTS response structure: {exc}") from exc

            if not audio_b64:
                raise RuntimeError("TTS response missing audio data")

            raw = base64.b64decode(audio_b64)

            # API returns raw PCM (audio/L16) — wrap in WAV so browsers can play it
            if mime_type.startswith("audio/L16") or mime_type.startswith("audio/pcm"):
                # Parse sample rate from mime type e.g. "audio/L16;codec=pcm;rate=24000"
                rate = 24000
                for part_str in mime_type.split(";"):
                    if part_str.strip().startswith("rate="):
                        try:
                            rate = int(part_str.strip().split("=")[1])
                        except ValueError:
                            pass
                return _pcm_to_wav(raw, sample_rate=rate), "audio/wav"

            return raw, mime_type

    except RuntimeError:
        raise
    except Exception as exc:
        logger.error("synthesize_speech failed: %s — %s", type(exc).__name__, exc)
        raise RuntimeError(f"TTS synthesis failed: {type(exc).__name__}: {exc}") from exc
