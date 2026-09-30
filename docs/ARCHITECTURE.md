# ARCHITECTURE

## 1. Style & topology
Modular monolith. Processes: `api` (FastAPI), `worker` (RQ: embeddings, Enrich, Monitor), `web` (Next.js).
Data: Neon Postgres 16 (+pgvector, pg_trgm) for development and deployment; Redis is introduced in Phase 3 and runs locally/self-hosted when needed. Solo + 4 weekends → boundaries are enforced by code layering, not network hops.

## 2. Layering
```
Interfaces   REST routers │ MCP server │ Agent tools │ Job handlers
     ↓  all call services; none run ORM writes directly
Services     app/modules/*/service.py — business rules, authz, audit
     ↓
Core         scoped repository, rbac, audit, db, errors, config
     ↓
Postgres (+pgvector) │ Redis
```
`context/` and `agents/` sit beside services: they call services/scoped repositories and are called only by interfaces/jobs.
Modules do not import each other's models (FKs by string); cross-module needs go through the other module's service. Exception: `identity`.

## 3. Actor & authorization
- `Actor(user_id, role, team_id, kind, agent_name)`; kinds: `human | agent | mcp | system`. Built once per request from the JWT (+ DB lookup for `is_active`/role freshness).
- **Delegation:** an agent/MCP call carries the delegating user's `user_id/role/team_id` plus `kind`. Permissions = that user's, further limited by the agent's tool allow-list. Audit records both.
- **Permission matrix** in code as data: `PERMISSIONS[role][resource] -> {read,create,update,delete}`. Rep: no delete, catalog read-only. Manager: team scope, can reassign owners. Admin: all.
- **Row visibility:** `visibility_clause(actor, Model)` → rep `owner_id==me`; manager `team_id==mine` (falls back to owner clause if team is NULL); admin true. Applied inside `ScopedRepository.get/list`; single-object fetch outside scope → 404.
- Ownership: create → owner = actor (manager/admin may assign); child docs inherit owner/team from parent; owner change is manager/admin only and cascades via service.

## 4. Transactions & audit
- Session per request/job. Services `flush()`; the dependency `Depends(get_session, scope="function")` commits before the response is sent, rolls back on exception. Jobs use an equivalent `unit_of_work()` context manager.
- `AuditLog(id, occurred_at, actor_id, actor_kind, agent_name, action, entity_type, entity_id, changes JSONB{field:[old,new]}, approval_id, run_id)`; written via `audit.record()` inside the service, same transaction. Immutable (no update/delete API).
- Use Python-side `default/onupdate` for timestamps so async responses never need server refreshes.

## 5. Data conventions
UUID PKs · tz-aware UTC · Decimal money · VARCHAR enums (values, not names) · naming convention for constraints in `MetaData` · FK columns indexed · JSONB via `JSON().with_variant(JSONB,"postgresql")` · emails lowercased, phones E.164 (normalize in service, not client) · hard delete only through gated admin action; prefer status/archive.

## 6. API conventions
`/api/v1`, plural nouns, `PATCH` = partial update, `Page{items,total,limit,offset}`, filters as query params, `Idempotency-Key` header on POST that agents/webhooks may retry, error envelope `{error:{code,message,details}}`, OpenAPI is the contract (frontend types generated from it), `/health` (liveness) and `/health/ready` (DB ping).

## 7. Context layer (Phase 2) — the product's brain
- **Activity is the atom.** Every interaction (email, chat, note, call transcript) is an `Activity` linked to an entity. Channel-agnostic.
- **Async pipeline** `process_activity` (RQ job on create): (1) Haiku → `ActivityInsight{summary, sentiment, intents[], next_steps[], entities{products,quantities,dates}}` stored in `meta`; (2) embed `summary + body head` → `embedding vector(N)` (+`embedding_model`), HNSW cosine index.
- **Entity resolution** (`context/resolution.py`): normalize keys (email, E.164 phone, domain); exact-key match → auto-link; fuzzy (pg_trgm name ≥0.6 + same domain/city) → `duplicate_candidate` with confidence. **Never auto-merge**; merge is a gated action.
- **Scoped retrieval** `retrieve(actor, query, entity=None, k=8)`: SQL `WHERE visibility AND entity` → `ORDER BY embedding <=> q LIMIT k` (enable `hnsw.iterative_scan` for filtered ANN), light recency rerank. Never search unscoped.
- **Context Pack** `build_context_pack(actor, entity, token_budget)` → deterministic, token-budgeted JSON: entity snapshot, relations, latest activity insights, open tasks/quotes/invoices, similar precedents. Trim oldest first. **Agents and MCP consume Context Packs, not raw tables.**
- **KB**: `kb_documents/kb_chunks` (pricing policy, product sheets), ~500-token chunks, same embedder. Used for product matching and policy explanations.
- `Embedder` protocol (provider swappable); dimension + model in settings.

## 8. Agent layer → docs/AGENT_LAYER.md

## 9. MCP server (Phase 5)
`app/mcp_server` wraps the same services (no duplicated logic). Transports: stdio (Claude Desktop) + streamable HTTP. Auth: personal access token → `Actor(kind=mcp)`.
Tools (schemas from Pydantic): read — `search_accounts, get_account_360 (Context Pack), pipeline_summary, stalled_deals, stock_check, list_pending_approvals`; write — only `draft_quotation` (creates draft + ApprovalRequest; never sends). Read-only default; every write gated.

## 10. Observability & cost
Request-id logging; `agent_runs` (steps JSONB, tokens, cost, latency) → UI "Agent Timeline"; audit log view. Redis rate-limit on LLM calls; per-run token cap.

## 11. Deployment

Docker Compose is introduced at deployment/packaging time (`api, worker, web, redis`) on one server; Caddy for TLS; secrets in server `.env`; optional nightly `pg_dump` to S3. Neon is the Postgres database for both development and deployment. Migrations run on deploy.

Local development: FastAPI and Next.js run directly on the machine (`uvicorn --reload`, `npm run dev`) and connect directly to Neon. No local Postgres or Docker is required for local development. Redis is skipped until Phase 3.

## 12. Testing strategy
Pure unit tests (pricing, policy, transitions) · service tests on real Postgres · API tests (RBAC matrix per role, audit written) · agent scenario tests with mocked LLM asserting **DB effects and approval requests, not prose** · `@pytest.mark.llm` live smoke tests (opt-in). Temperature 0 for agents.

## 13. LLM provider
Use either **OpenAI or Gemini**, selected through environment configuration.
Keep `agents/llm.py` provider-agnostic so the provider and model can be changed through settings without changing agent logic.
API keys must come from environment variables and must never be committed or logged.

## 14. Deployment — free/low-cost topology

- **DB:** Neon free tier (Postgres 16, pgvector included, 0.5 GB storage / 100 CU-hrs monthly — well above this project's seed-data scale). Autosuspends when idle; first request after idle has a brief cold start.
- **Redis:** introduced in Phase 3; self-hosted container next to the deployed app. Upstash free tier is a drop-in alternative if a fully managed stack is preferred.
- **Compute (api, worker, web):** the user's existing Linux server if it has root/Docker access and ≥2 GB RAM — zero new signup, reuses paid-for infra. Otherwise, Oracle Cloud "Always Free" Ampere A1; AWS EC2 free tier is the fallback.
- **Local development:** FastAPI + Next.js run natively; both connect directly to Neon via `DATABASE_URL`. No local Postgres, Redis, or Docker is required during development. Docker Compose is added later for deployment/packaging.