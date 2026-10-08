.PHONY: up down dev worker migrate revision seed test lint fmt

# Docker Compose is deployment/packaging scaffolding only — NOT required for local development.
# Local dev connects straight to Neon via DATABASE_URL in .env.
up:
	docker compose up -d db redis

down:
	docker compose down

dev:
	cd backend && uvicorn app.main:app --reload

# Processes process_activity jobs. Needs a Redis-compatible server on REDIS_URL (`make up`,
# or a native/Memurai install for local dev — see docs/ARCHITECTURE.md §1).
worker:
	cd backend && rq worker activities --url "$${REDIS_URL:-redis://localhost:6379/0}"

migrate:
	cd backend && alembic upgrade head

revision:
	cd backend && alembic revision --autogenerate -m "$(m)"

seed:
	cd backend && python -m app.scripts.seed

# Runs migrations against TEST_DATABASE_URL (never DATABASE_URL), then the suite.
test:
	cd backend && QUOTEPULSE_ALEMBIC_DB=test alembic upgrade head && pytest

lint:
	cd backend && ruff check . && ruff format --check . && mypy app/core

fmt:
	cd backend && ruff format . && ruff check --fix .
