"""
One-shot indexer script for CEFIS AI Tutor.

Reads transcript VTT files from TRANSCRIPTS_PATH, chunks the text,
generates embeddings via Gemini, and inserts into Supabase.

Idempotent: exits immediately if transcript_chunks already has rows.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
TRANSCRIPTS_PATH = os.environ.get("TRANSCRIPTS_PATH", "/data/Transcricoes/courses/output")

_EMBED_MODEL = "gemini-embedding-001"
_EMBED_DIMS = 768

# Chunking parameters (word-based approximation: 1 token ≈ 0.75 words)
_CHUNK_WORDS = 667   # ~500 tokens
_OVERLAP_WORDS = 67  # ~50 tokens

_BATCH_SIZE = 100

# ---------------------------------------------------------------------------
# Gemini sync embed
# ---------------------------------------------------------------------------

_gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def embed(text: str) -> list[float]:
    """Generate a 768-dimensional embedding for the given text (synchronous)."""
    response = _gemini_client.models.embed_content(
        model=_EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=_EMBED_DIMS),
    )
    return response.embeddings[0].values


# ---------------------------------------------------------------------------
# VTT parsing
# ---------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}"
)


def parse_vtt(vtt_text: str) -> str:
    """
    Strip WEBVTT header, cue numbers, and timestamp lines.
    Return concatenated spoken text lines.
    """
    lines = vtt_text.splitlines()
    text_lines: list[str] = []
    skip_header = True

    for line in lines:
        stripped = line.strip()

        # Skip the WEBVTT header block at the top
        if skip_header:
            if stripped.startswith("WEBVTT"):
                continue
            elif stripped == "":
                skip_header = False
                continue
            else:
                skip_header = False

        # Skip blank lines
        if not stripped:
            continue

        # Skip cue numbers (pure integers)
        if stripped.isdigit():
            continue

        # Skip timestamp lines
        if _TIMESTAMP_RE.match(stripped):
            continue

        # Skip NOTE, STYLE, REGION blocks
        if stripped.startswith(("NOTE", "STYLE", "REGION")):
            continue

        text_lines.append(stripped)

    return " ".join(text_lines)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_words: int = _CHUNK_WORDS, overlap_words: int = _OVERLAP_WORDS) -> list[str]:
    """
    Split text into overlapping chunks of approximately chunk_words words.
    Returns a list of text chunks.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_words - overlap_words

    return chunks


# ---------------------------------------------------------------------------
# Transcript discovery
# ---------------------------------------------------------------------------

def iter_lessons(transcripts_path: str):
    """
    Yield dicts with course_id, course_name, lesson_id, lesson_name, text
    for every lesson that has a subtitle_pt-BR.vtt file.
    """
    base = Path(transcripts_path)
    if not base.exists():
        logger.error("TRANSCRIPTS_PATH does not exist: %s", transcripts_path)
        return

    course_dirs = sorted(p for p in base.iterdir() if p.is_dir())
    logger.info("Found %d course directories", len(course_dirs))

    for course_dir in course_dirs:
        course_details_path = course_dir / "details.json"
        if not course_details_path.exists():
            logger.warning("Skipping %s — no details.json", course_dir.name)
            continue

        try:
            with open(course_details_path, encoding="utf-8") as f:
                course_data = json.load(f)
            course_id = str(course_data["data"]["id"])
            course_name = course_data["data"]["title"]
        except Exception as exc:
            logger.warning("Skipping course %s — failed to read details.json: %s", course_dir.name, exc)
            continue

        lessons_dir = course_dir / "lessons"
        if not lessons_dir.exists():
            continue

        lesson_dirs = sorted(p for p in lessons_dir.iterdir() if p.is_dir())
        for lesson_dir in lesson_dirs:
            vtt_path = lesson_dir / "subtitle_pt-BR.vtt"
            if not vtt_path.exists():
                # Silently skip lessons without transcripts
                continue

            lesson_details_path = lesson_dir / "details.json"
            if not lesson_details_path.exists():
                logger.warning("Skipping lesson %s/%s — no details.json", course_dir.name, lesson_dir.name)
                continue

            try:
                with open(lesson_details_path, encoding="utf-8") as f:
                    lesson_data = json.load(f)
                lesson_id = str(lesson_data["id"])
                lesson_name = lesson_data["title"]
            except Exception as exc:
                logger.warning(
                    "Skipping lesson %s/%s — failed to read details.json: %s",
                    course_dir.name, lesson_dir.name, exc,
                )
                continue

            try:
                with open(vtt_path, encoding="utf-8") as f:
                    vtt_text = f.read()
                text = parse_vtt(vtt_text)
            except Exception as exc:
                logger.warning(
                    "Skipping lesson %s/%s — failed to read VTT: %s",
                    course_dir.name, lesson_dir.name, exc,
                )
                continue

            if not text.strip():
                logger.warning(
                    "Skipping lesson %s/%s — empty transcript after parsing",
                    course_dir.name, lesson_dir.name,
                )
                continue

            yield {
                "course_id": course_id,
                "course_name": course_name,
                "lesson_id": lesson_id,
                "lesson_name": lesson_name,
                "text": text,
            }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def check_already_indexed(supabase: Client) -> bool:
    """Return True if transcript_chunks already has rows."""
    result = (
        supabase.table("transcript_chunks")
        .select("id", count="exact")
        .limit(1)
        .execute()
    )
    count = result.count if result.count is not None else 0
    return count > 0


def run_indexer() -> None:
    logger.info("Starting CEFIS transcript indexer")
    logger.info("TRANSCRIPTS_PATH: %s", TRANSCRIPTS_PATH)

    # Init Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Idempotency check
    if check_already_indexed(supabase):
        logger.info("transcript_chunks already has rows — nothing to do. Exiting.")
        sys.exit(0)

    # Collect all chunks across all lessons
    all_chunks: list[dict] = []
    total_courses: set[str] = set()
    total_lessons = 0

    for lesson in iter_lessons(TRANSCRIPTS_PATH):
        total_courses.add(lesson["course_id"])
        total_lessons += 1

        chunks = chunk_text(lesson["text"])
        logger.debug(
            "Course %s | Lesson %s (%s) → %d chunks",
            lesson["course_id"], lesson["lesson_id"], lesson["lesson_name"], len(chunks),
        )

        for chunk in chunks:
            all_chunks.append({
                "course_id": lesson["course_id"],
                "course_name": lesson["course_name"],
                "lesson_id": lesson["lesson_id"],
                "lesson_name": lesson["lesson_name"],
                "content": chunk,
            })

    logger.info(
        "Discovered %d courses, %d lessons, %d total chunks",
        len(total_courses), total_lessons, len(all_chunks),
    )

    if not all_chunks:
        logger.warning("No chunks to index. Check TRANSCRIPTS_PATH and VTT files.")
        sys.exit(0)

    # Process in batches: embed + insert
    total_batches = (len(all_chunks) + _BATCH_SIZE - 1) // _BATCH_SIZE
    inserted = 0

    for batch_idx in range(total_batches):
        start = batch_idx * _BATCH_SIZE
        end = min(start + _BATCH_SIZE, len(all_chunks))
        batch = all_chunks[start:end]

        logger.info(
            "Processing batch %d/%d (chunks %d–%d)",
            batch_idx + 1, total_batches, start + 1, end,
        )

        rows: list[dict] = []
        for chunk_data in batch:
            try:
                embedding = embed(chunk_data["content"])
                rows.append({
                    "course_id": chunk_data["course_id"],
                    "lesson_id": chunk_data["lesson_id"],
                    "course_name": chunk_data["course_name"],
                    "lesson_name": chunk_data["lesson_name"],
                    "content": chunk_data["content"],
                    "embedding": embedding,
                })
            except Exception as exc:
                logger.error(
                    "Failed to embed chunk for lesson %s: %s — skipping",
                    chunk_data["lesson_id"], exc,
                )

        if not rows:
            logger.warning("Batch %d/%d: all embeddings failed, skipping insert", batch_idx + 1, total_batches)
            continue

        try:
            supabase.table("transcript_chunks").insert(rows).execute()
            inserted += len(rows)
            logger.info(
                "Batch %d/%d: inserted %d rows (total so far: %d)",
                batch_idx + 1, total_batches, len(rows), inserted,
            )
        except Exception as exc:
            logger.error("Failed to insert batch %d/%d: %s", batch_idx + 1, total_batches, exc)

    logger.info("Indexing complete. Total rows inserted: %d", inserted)


if __name__ == "__main__":
    run_indexer()
