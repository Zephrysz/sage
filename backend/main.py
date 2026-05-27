from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

from routers import session, chat, diagnosis, plan, content
from config import settings

app = FastAPI(
    title="CEFIS AI Tutor",
    description="Personalized AI tutor backed by CEFIS course catalog and Gemini.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(session.router, prefix="/session", tags=["session"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(diagnosis.router, prefix="/diagnosis", tags=["diagnosis"])
app.include_router(plan.router, prefix="/plan", tags=["plan"])
app.include_router(content.router, prefix="/content", tags=["content"])


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/debug/session/{session_id}", tags=["debug"])
async def debug_session(session_id: str) -> dict:
    """Dev-only: inspect raw session state."""
    from session_store import get_session
    session = get_session(session_id)
    if session is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    safe = {k: v for k, v in session.items() if k != "cefis_api_key"}
    return safe


@app.post("/debug/seed-session", tags=["debug"])
async def seed_session(body: dict = {}) -> dict:
    """
    Dev-only: create a session already in PLAN_READY state with a fake
    profile and diagnosis so you can test GET /plan directly.

    Optional body fields:
      - cefis_api_key: str   — forwarded to CEFIS API calls (default: "")
      - goal: str            — student goal (default: "Analista de dados")
      - level: str           — iniciante | intermediario | avancado
      - time_available: int  — minutes (default: 60)
      - learning_style: str  — video | leitura | audio
    """
    import uuid
    from datetime import datetime
    from session_store import create_session

    session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    session_data = {
        "id": session_id,
        "state": "PLAN_READY",
        "cefis_api_key": body.get("cefis_api_key", ""),
        "user": {"name": "Aluno Teste"},
        "profile": {
            "goal": body.get("goal", "Analista de dados"),
            "level": body.get("level", "iniciante"),
            "time_available": int(body.get("time_available", 60)),
            "learning_style": body.get("learning_style", "video"),
        },
        "diagnosis": {
            "level": "iniciante",
            "score": 0.2,
            "gaps": [
                {"topic": "SQL e consultas relacionais", "is_critical": True,  "wrong_count": 3},
                {"topic": "Python para análise de dados",  "is_critical": False, "wrong_count": 2},
                {"topic": "Visualização de dados",         "is_critical": False, "wrong_count": 1},
            ],
        },
        "study_plan": None,
        "chat_history": [],
        "current_course_id": None,
        "created_at": now,
        "updated_at": now,
    }

    create_session(session_id, session_data)
    return {"session_id": session_id, "state": "PLAN_READY"}
