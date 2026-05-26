"""
Diagnosis router — POST /diagnosis/start and POST /diagnosis/submit

Handles the MCQ-based knowledge diagnosis phase.

POST /diagnosis/start
    - Fetches student certificates from CEFIS API
    - Generates 3–5 MCQ questions via Gemini structured output
    - Stores questions (with correct_answer) in session
    - Returns questions to frontend WITHOUT correct_answer
    - On Gemini failure: returns fallback=true, sets DiagnosisResult(INICIANTE, gaps=[]),
      transitions state to PLAN_READY

POST /diagnosis/submit
    - Receives answers dict {question_id: "A"|"B"|"C"|"D"}
    - Validates each answer is A/B/C/D
    - Calculates score and DiagnosisLevel
    - Identifies gaps (wrong answers → topic, is_critical if 0% on topic)
    - Stores DiagnosisResult in session
    - Transitions state to PLAN_READY
    - Returns result WITHOUT correct_answer fields
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from models.diagnosis import DiagnosisLevel, DiagnosisResult, Gap
from models.session import SessionState
from services import gemini_service
from session_store import get_session, update_session

logger = logging.getLogger(__name__)

router = APIRouter()
class SubmitAnswersRequest(BaseModel):
    answers: dict[str, str]  # {question_id: "A"|"B"|"C"|"D"}

_VALID_ANSWERS = {"A", "B", "C", "D", "E"}


def _score_to_level(score: float) -> DiagnosisLevel:
    """Map a 0.0–1.0 score to a DiagnosisLevel."""
    if score <= 0.40:
        return DiagnosisLevel.INICIANTE
    elif score <= 0.70:
        return DiagnosisLevel.INTERMEDIARIO
    else:
        return DiagnosisLevel.AVANCADO


def _questions_to_session_dict(questions: list) -> list[dict]:
    """Serialize DiagnosisQuestion list to dicts for session storage (includes correct_answer)."""
    result = []
    for q in questions:
        result.append({
            "id": str(q.id),
            "text": q.text,
            "options": {
                "A": q.options.A,
                "B": q.options.B,
                "C": q.options.C,
                "D": q.options.D,
                "E": q.options.E,
            },
            "correct_answer": q.correct_answer,
            "topic": q.topic,
        })
    return result


def _questions_to_frontend(questions_dicts: list[dict]) -> list[dict]:
    """Strip correct_answer before sending to frontend."""
    return [
        {
            "id": q["id"],
            "text": q["text"],
            "options": q["options"],
            "topic": q["topic"],
        }
        for q in questions_dicts
    ]


@router.post("/start")
async def diagnosis_start(
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> dict:
    """
    Start the diagnosis phase.

    Fetches certificates, generates MCQ questions via Gemini, stores them
    in session, and returns them to the frontend (without correct_answer).

    On Gemini failure: returns fallback=true and transitions to PLAN_READY
    with DiagnosisResult(level=INICIANTE, score=0.0, gaps=[]).
    """
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = session.get("profile") or {}
    goal = profile.get("goal", "")
    level = profile.get("level", "iniciante")

    questions = await gemini_service.generate_mcq_questions(
        goal=goal,
        level=level,
        n=5,
    )

    if not questions:
        fallback_result = DiagnosisResult(
            level=DiagnosisLevel.INICIANTE,
            score=0.0,
            gaps=[],
        )
        update_session(
            x_session_id,
            {
                "diagnosis": fallback_result.model_dump(mode="json"),
                "state": SessionState.PLAN_READY.value,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        return {"fallback": True, "questions": []}

    questions_dicts = _questions_to_session_dict(questions)
    update_session(
        x_session_id,
        {
            "diagnosis_questions": questions_dicts,
            "state": SessionState.DIAGNOSIS.value,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )

    return {
        "fallback": False,
        "questions": _questions_to_frontend(questions_dicts),
    }


@router.post("/submit")
async def diagnosis_submit(
    body: SubmitAnswersRequest,
    x_session_id: str = Header(..., alias="X-Session-Id"),
) -> dict:
    """
    Submit answers for the diagnosis questions.

    Validates answers, calculates score, determines level, identifies gaps,
    stores DiagnosisResult in session, and transitions to PLAN_READY.

    Returns the diagnosis result without correct_answer fields.
    """
    session = get_session(x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    questions: list[dict] = session.get("diagnosis_questions") or []
    if not questions:
        raise HTTPException(
            status_code=400,
            detail="No diagnosis questions found. Call /diagnosis/start first.",
        )

    answers = body.answers

    invalid_answers = {
        qid: ans
        for qid, ans in answers.items()
        if ans.upper() not in _VALID_ANSWERS
    }
    if invalid_answers:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Respostas inválidas: {list(invalid_answers.values())}. "
                "Por favor, escolha entre as opções A, B, C, D ou E."
            ),
        )

    answers_upper = {qid: ans.upper() for qid, ans in answers.items()}

    question_map = {q["id"]: q for q in questions}

    correct_count = 0
    total = len(questions)

    topic_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    wrong_questions: list[dict] = []

    for q in questions:
        qid = q["id"]
        topic = q["topic"]
        correct_answer = q["correct_answer"]
        student_answer = answers_upper.get(qid)

        topic_stats[topic]["total"] += 1

        if student_answer == correct_answer:
            correct_count += 1
            topic_stats[topic]["correct"] += 1
        else:
            wrong_questions.append(q)

    score = correct_count / total if total > 0 else 0.0
    level = _score_to_level(score)

    gaps_by_topic: dict[str, Gap] = {}
    for q in wrong_questions:
        topic = q["topic"]
        if topic not in gaps_by_topic:
            stats = topic_stats[topic]
            is_critical = stats["correct"] == 0
            gaps_by_topic[topic] = Gap(
                topic=topic,
                is_critical=is_critical,
                wrong_count=0,
            )
        gaps_by_topic[topic] = Gap(
            topic=topic,
            is_critical=gaps_by_topic[topic].is_critical,
            wrong_count=gaps_by_topic[topic].wrong_count + 1,
        )

    gaps = list(gaps_by_topic.values())

    result = DiagnosisResult(level=level, score=score, gaps=gaps)
    update_session(
        x_session_id,
        {
            "diagnosis": result.model_dump(mode="json"),
            "state": SessionState.PLAN_READY.value,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )

    sorted_gaps = sorted(gaps, key=lambda g: (-int(g.is_critical), -g.wrong_count))
    top_gaps = sorted_gaps[:3]

    return {
        "level": level.value,
        "score": round(score, 4),
        "gaps": [
            {
                "topic": g.topic,
                "is_critical": g.is_critical,
                "wrong_count": g.wrong_count,
            }
            for g in top_gaps
        ],
        "total_questions": total,
        "correct_answers": correct_count,
    }
