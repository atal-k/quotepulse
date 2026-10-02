# PHASE NOTES

Detailed per-phase change reports (file-by-file). `docs/CHANGELOG.md` stays one line per
feature/architecture change; this file keeps the full report for reference.

## Phase 0

### Changes
- `Makefile`, `docker-compose.yml`, `backend/Dockerfile`, `.env.example`, `README.md` — repo skeleton: dev commands, deployment-only Compose scaffolding, env template, setup docs
- `backend/pyproject.toml` — package config, deps (fastapi, sqlalchemy[asyncio], asyncpg, alembic, pydantic(-settings), argon2-cffi, pyjwt, email-validator), ruff/mypy/pytest config
- `backend/app/core/config.py` — pydantic-settings `Settings`, `SecretStr` for connection strings/JWT secret so they never leak into error tracebacks or logs
- `backend/app/core/db.py` — async engine/session factory, `get_session` (commits on success, rolls back on exception), `build_engine()` normalizes a plain Neon `postgresql://` URL to `+asyncpg` and strips `sslmode`/`channel_binding` into `connect_args`
- `backend/app/core/base.py` — `DeclarativeBase`, naming convention, `UUIDPkMixin`/`TimestampMixin` (Python-side default/onupdate)
- `backend/app/core/security.py` — argon2 hashing, JWT encode/decode
- `backend/app/core/rbac.py` — `Actor`, `Role`/`ActorKind`/`Action`, permission matrix, `visibility_clause()` (rep=own, manager=team w/ null-team fallback, admin=all)
- `backend/app/core/audit.py` — `AuditLog` model + `record()`, immutable, same-transaction
- `backend/app/core/errors.py` — 5 domain exceptions + `Unauthorized` (401, not one of the documented 5 — auth-layer, not business-rule) + `StarletteHTTPException`/`RequestValidationError`/catch-all handlers, all to the `{error:{code,message,details}}` envelope
- `backend/app/core/pagination.py`, `backend/app/core/logging.py` — `Page`/`PageParams`, request-id middleware
- `backend/app/modules/base.py` — generic `CrudService` (get/list/create/update only — no delete; see Notes)
- `backend/app/modules/identity/*` — `Team`/`User` models, login+`/me`, `get_current_actor`/`get_current_user` dependencies
- `backend/app/modules/accounts/*` — reference CRUD slice; `AccountService` enforces ownership rules (rep can't self-assign a different owner; manager/admin can reassign)
- `backend/app/main.py` — app factory, exception handlers, CORS+request-id middleware, `/health`, `/health/ready`
- `backend/app/scripts/seed.py` — idempotent 1 team + admin/manager/rep users
- `backend/alembic/*`, `backend/alembic/versions/e2b6594c7d63_*.py` — async env (Neon-aware, dev/test switch via `QUOTEPULSE_ALEMBIC_DB`), first migration (`teams`, `users`, `accounts`, `audit_logs`) generated via `alembic revision --autogenerate` against the real dev DB, reviewed before applying
- `backend/tests/*` — RBAC-scoping, 404-not-403, audit-row, and auth-flow tests on real Postgres via SAVEPOINT-per-test isolation
- `docs/ROADMAP.md`, `docs/CHANGELOG.md` — Phase 0 boxes ticked, changelog entry added

### Verification
- `ruff check` / `ruff format --check` / `mypy app/core` → all clean (ran directly; no `make` binary on this machine — see Notes)
- `alembic upgrade head` against `DATABASE_URL` (Neon) → applied cleanly, created all 4 tables with correct FKs/indexes/naming convention
- `python -m app.scripts.seed` → seeded admin/manager/rep + 1 team
- `pytest` against `TEST_DATABASE_URL` → **18/18 passed**, real Postgres, no mocks

### Notes
- **`make` isn't installed on this machine** — I ran the Makefile's underlying commands directly (`ruff`/`mypy`/`alembic`/`pytest` via the venv) rather than `make lint`/`make test` themselves. The Makefile targets are correct and will work once `make` is available (WSL, Git-for-Windows' optional make, or CI).
- **`TEST_DATABASE_URL` currently equals `DATABASE_URL`** (same Neon database) — you chose to proceed this way rather than provision a second DB/branch. Tests pass and roll back via SAVEPOINT so nothing persists, but this is a live deviation from CLAUDE.md's "separate test DB" rule; worth fixing before Phase 1 adds more state-mutating tests.
- **No delete on `accounts`** — DOMAIN.md requires hard deletes go through a gated admin action, which doesn't exist until the Phase 4 approvals module. Adding delete now would mean either an ungated destructive endpoint (violates Rule 8) or half-building approvals early (premature). `CrudService` has no `delete()`; add it alongside `policy.decide()`/`ApprovalRequest` in Phase 4.
- **New deps beyond the fixed stack** (one-line justification each, per CLAUDE.md §3): `argon2-cffi` (direct, maintained — implements the mandated argon2 hashing; `passlib` is unmaintained), `pyjwt` (small, maintained — implements the mandated short-lived JWT; avoids `python-jose`'s CVE history), `email-validator` (required by Pydantic's `EmailStr` for input validation on login).
- **Verification ran under Python 3.14**, not 3.12 — only 3.14 is installed on this machine. `pyproject.toml` declares `requires-python = ">=3.12"` (not pinned to exactly 3.12), so this is compatible, but flagging since CLAUDE.md names 3.12 specifically.
- **Housekeeping bugs found and fixed during verification** (all now covered by the green test run): `SecretStr` hardening after a pydantic validation-error traceback briefly echoed a truncated settings fragment; a stray duplicate `backend/.env` (from my own earlier wording in the setup question) got consolidated into the canonical root `.env` and removed; `Page[Account]` as a router return-type annotation crashed at import time under Python 3.14's eager annotation evaluation (pydantic tried to build a schema for the raw ORM class) — fixed to an unparameterized `Page`; a session-scoped test-engine fixture broke across pytest-asyncio's per-test event loops — now function-scoped; one Starlette status-constant rename (`HTTP_422_UNPROCESSABLE_ENTITY` → `_CONTENT`).
- `.gitignore` currently excludes `CLAUDE.md`, `AGENTS.md`, `ROADMAP.md`, and `docs/CHANGELOG.md` from git — I updated `docs/ROADMAP.md`/`docs/CHANGELOG.md` per CLAUDE.md's mandate anyway, but flagging that they won't actually get committed under the current `.gitignore` if you `git add` broadly.
- Nothing committed — per CLAUDE.md §6, commits happen only when you ask.

## Phase 0 → Phase 1 Handoff

**Completed:** repo skeleton, `core/` foundation (config/db/base/security/rbac/audit/errors/pagination/logging), generic `CrudService`, `identity` (login+`/me`) and `accounts` (reference CRUD slice) modules, async Alembic env + first migration (`teams`, `users`, `accounts`, `audit_logs`), idempotent seed script, test harness on real Postgres. Pushed to `github.com/atal-k/quotepulse` (branded QuotePulse; repo dir stays `quotient/`).

**Current state:** `ruff`/`mypy`/`alembic upgrade head`/seed/`pytest` all verified green (18/18 tests) against Neon. `make` now installed and confirmed working (`make test` passes). Seeded users: `admin@quotepulse.dev` / `manager@quotepulse.dev` / `rep@quotepulse.dev` (Aditya Sharma / Priya Nair / Rohan Verma), 1 team.

**Key decisions to respect in Phase 1:**
- `CrudService` (get/list/create/update only, no delete) is the pattern for simple aggregates (`contacts`, `products`, `notifications`); ROADMAP 1B modules (`quotations`, `orders`, `invoices`) need dedicated services, not this base class.
- `visibility_clause()` in `core/rbac.py` requires `owner_id`+`team_id` on every owned model — keep denormalizing those on new tables.
- Ownership-reassignment pattern (`prepare_create`/`authorize_update` hooks in `AccountService`) is the template for any module with manager/admin-only field changes.
- No delete anywhere until Phase 4's approvals/gating exists — don't add one-off delete endpoints in Phase 1.
- Audit every mutation via `core/audit.record()` in the same transaction — already wired into `CrudService.create`/`update`, extend to dedicated Phase 1B services manually.

**Known limitation — fix before Phase 1 adds more tests:** `TEST_DATABASE_URL` currently equals `DATABASE_URL` (same Neon DB). Tests pass via SAVEPOINT rollback so nothing persists, but this deviates from CLAUDE.md's "separate test DB" rule. Provision a second Neon DB/branch and update `.env` before Phase 1's larger test surface (quotations, stock concurrency, etc.) lands.

**Other follow-ups:** `pg_trgm` extension not yet enabled (ROADMAP 1A says do it early in Phase 1, it's cheap). Verification so far ran under Python 3.14 (only version installed here), not the pinned 3.12 — compatible per `requires-python>=3.12` but worth installing 3.12 if strict parity matters. `git commit`/push must never include a Claude co-author trailer — author stays `atal-k` only.
