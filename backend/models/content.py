from enum import Enum
from uuid import UUID
from pydantic import BaseModel


class ContentType(str, Enum):
    SUMMARY = "SUMMARY"
    APOSTILA = "APOSTILA"
    PODCAST = "PODCAST"


class ContentSource(BaseModel):
    course_name: str
    lesson_name: str


class GeneratedContent(BaseModel):
    id: UUID
    type: ContentType
    plan_item_id: str
    text: str
    audio_url: str | None = None
    search_sources: list[str] = []
    indexed: bool = False
    rag_sourced: bool = True
