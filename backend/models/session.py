from enum import Enum
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class SessionState(str, Enum):
    ONBOARDING = "ONBOARDING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    DIAGNOSIS = "DIAGNOSIS"
    PLAN_READY = "PLAN_READY"
    STUDY_MODE = "STUDY_MODE"


class ExperienceLevel(str, Enum):
    INICIANTE = "iniciante"
    INTERMEDIARIO = "intermediario"
    AVANCADO = "avancado"


class LearningStyle(str, Enum):
    VIDEO = "video"
    LEITURA = "leitura"
    AUDIO = "audio"


class Profile(BaseModel):
    area: str
    goal: str
    level: ExperienceLevel
    time_available: int # minutes
    learning_style: LearningStyle


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime


class Session(BaseModel):
    id: UUID
    state: SessionState
    user: dict | None = None
    profile: Profile | None = None
    diagnosis: "DiagnosisResult | None" = None
    study_plan: "StudyPlan | None" = None
    chat_history: list[ChatMessage] = []
    current_course_id: str | None = None
    created_at: datetime
    updated_at: datetime


# Resolve forward references after all models are defined
from models.diagnosis import DiagnosisResult  # noqa: E402
from models.plan import StudyPlan             # noqa: E402

Session.model_rebuild()
