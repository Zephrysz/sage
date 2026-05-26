from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import session, chat, diagnosis, plan, content

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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3333",
    ],
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
    # Omit the CEFIS api key from the response
    safe = {k: v for k, v in session.items() if k != "cefis_api_key"}
    return safe
