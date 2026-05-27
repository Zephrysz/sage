from enum import Enum
from uuid import UUID
from pydantic import BaseModel


class PlanItemType(str, Enum):
    CEFIS_COURSE = "CEFIS_COURSE"
    GENERATED_CONTENT = "GENERATED_CONTENT"


class PlanItem(BaseModel):
    id: UUID
    position: int
    type: PlanItemType
    title: str
    estimated_minutes: int
    justification: str
    course_id: str | None = None
    course_details: dict | None = None
    has_certificate: bool = False
    highlighted_lessons: list[str] = []  # lesson titles to highlight when course > session time


class StudyPlan(BaseModel):
    items: list[PlanItem]
    total_estimated_minutes: int
