from enum import Enum
from uuid import UUID
from pydantic import BaseModel


class DiagnosisOptions(BaseModel):
    A: str
    B: str
    C: str
    D: str
    E: str


class DiagnosisQuestion(BaseModel):
    id: UUID
    text: str
    options: DiagnosisOptions
    correct_answer: str
    topic: str


class Gap(BaseModel):
    topic: str
    is_critical: bool
    wrong_count: int


class DiagnosisLevel(str, Enum):
    INICIANTE = "iniciante"
    INTERMEDIARIO = "intermediario"
    AVANCADO = "avancado"


class DiagnosisResult(BaseModel):
    level: DiagnosisLevel
    score: float                     # 0.0–1.0
    gaps: list[Gap]
