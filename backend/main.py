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
