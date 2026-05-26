COMPOSE_DEV  = docker compose -f docker-compose.dev.yml
COMPOSE_PROD = docker compose -f docker-compose.prod.yml
ENV_FILE     = backend/.env
MIGRATIONS   = supabase/migrations
PROJECT_REF  = vuoufotchddtzeqcfokf

.DEFAULT_GOAL := help

.PHONY: help up down restart build logs ps up-prod down-prod build-prod migrate-run

help:
	@echo ""
	@echo "  make up          Start dev environment"
	@echo "  make down        Stop and remove containers"
	@echo "  make restart     Restart all services"
	@echo "  make build       Rebuild images (no cache)"
	@echo "  make logs        Tail logs for all services"
	@echo "  make ps          Show running containers"
	@echo "  make migrate-run Run SQL migrations against Supabase"
	@echo ""
	@echo "  Prod variants: make up-prod  down-prod  build-prod"
	@echo ""

# ── Dev ──────────────────────────────────────────────────────────────────────

up:
	$(COMPOSE_DEV) up

down:
	$(COMPOSE_DEV) down

restart:
	$(COMPOSE_DEV) restart

build:
	$(COMPOSE_DEV) build --no-cache

logs:
	$(COMPOSE_DEV) logs -f

ps:
	$(COMPOSE_DEV) ps

# ── Prod ─────────────────────────────────────────────────────────────────────

up-prod:
	$(COMPOSE_PROD) up -d

down-prod:
	$(COMPOSE_PROD) down

build-prod:
	$(COMPOSE_PROD) build --no-cache

# ── Database ─────────────────────────────────────────────────────────────────

migrate-run:
	supabase db push $(PROJECT_REF)
