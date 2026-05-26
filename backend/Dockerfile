# ============================================================
# Stage: base — install uv and sync dependencies into venv
# ============================================================
FROM python:3.12-slim AS base

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# System deps required by some packages (e.g. cryptography, grpcio)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock* ./

# Create venv and install all dependencies (no dev group in prod)
RUN uv sync --frozen --no-dev

# Copy application source
COPY . .

# ============================================================
# Stage: development — hot reload, dev deps included
# ============================================================
FROM base AS development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Re-sync with dev dependencies (hypothesis, pytest, etc.)
RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================
# Stage: production — 2 workers, no reload, no dev deps
# ============================================================
FROM base AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
