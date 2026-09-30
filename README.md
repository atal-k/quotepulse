# QuotePulse

AI-native CRM for industrial sales workflows (Lead → Opportunity → Quotation → Order → Invoice).
Repository: [github.com/atal-k/quotepulse](https://github.com/atal-k/quotepulse). See `CLAUDE.md`
for the full architecture and `docs/` for domain, agent-layer and roadmap detail.

## Local development

Backend and frontend run natively on your machine; both talk directly to **Neon Postgres**. No local
Postgres, Redis, or Docker is required for development — Docker Compose is deployment scaffolding only.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Copy `.env.example` (repo root) to `.env` and fill in:
- `DATABASE_URL` — your Neon dev database (asyncpg URL, `?sslmode=require`)
- `TEST_DATABASE_URL` — a **separate** Neon database/branch used only by `make test`
- `JWT_SECRET` — any long random string (`openssl rand -hex 32`)

Then, from the repo root:

```bash
make migrate   # alembic upgrade head, against DATABASE_URL
make seed      # creates 1 team + admin/manager/rep users
make dev       # uvicorn --reload on http://localhost:8000
make test      # migrates + runs pytest against TEST_DATABASE_URL
make lint      # ruff + mypy (app/core)
```

### Seeded users (dev only — not real secrets)

| Role    | Email                | Password        |
|---------|-----------------------|------------------|
| admin   | admin@quotepulse.dev    | admin-12345      |
| manager | manager@quotepulse.dev  | manager-12345    |
| rep     | rep@quotepulse.dev      | rep-12345        |

`POST /api/v1/auth/login {email, password}` → `{access_token, token_type}`. Send it as
`Authorization: Bearer <token>` on subsequent requests, e.g. `GET /api/v1/me`.

### Frontend

Not scaffolded yet — arrives in Phase 1 (see `docs/ROADMAP.md`).
