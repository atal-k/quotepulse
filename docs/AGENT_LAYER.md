# AGENT LAYER (runtime agents of the product)

## 1. Principles
1. LLM proposes, code disposes. 2. Typed tools only. 3. Scoped: agent acts as the delegating user. 4. Auditable: runs, steps, tool calls, approvals persisted.
5. Bounded: ≤6 tool iterations, 60 s timeout, per-run token cap; on failure → fail closed to a human. 6. Deterministic first (rules/SQL), LLM only for language, extraction, mapping, judgment. 7. Cheapest sufficient model.

## 2. Runtime components (`app/agents/`)
| File | Responsibility |
|---|---|
| `runtime.py` | `AgentRun` lifecycle: queued → running → awaiting_approval → succeeded/failed/cancelled; step log; token/cost accounting |
| `tools.py` | Registry: `Tool(name, input_model, output_model, side_effect=READ/WRITE/GATED, handler→service)`. Each agent has an explicit allow-list |
| `policy.py` | Pure `decide(actor, action, payload) → ALLOW | REQUIRE_APPROVAL(approver_role) | DENY`. Single source of HITL truth; unit-tested |
| `executor.py` | On approval: re-validate payload + entity version (optimistic lock) → call service as **human** Actor with `approval_id` → audit. Idempotent |
| `llm.py` | Anthropic wrapper: structured output → Pydantic, retry once on invalid, timeouts, tier by config (`MODEL_REASONING`, `MODEL_FAST`), records tokens/latency |
| `prompts/*.md` | Versioned prompts. Untrusted content wrapped in `<untrusted_content>` delimiters |
`approvals` module: `ApprovalRequest(id, agent_run_id, action, payload JSONB, entity ref, status pending/approved/rejected/expired/executed, approver_role, requested_by, decided_by, decided_at, note, idempotency_key, expires_at)`.

## 3. Approval flow
```
Agent tool call → policy.decide()
   ├─ ALLOW ─────────────► service (as delegating user) ─► audit(actor.kind=agent)
   ├─ DENY ──────────────► error returned to agent (logged)
   └─ REQUIRE_APPROVAL ──► ApprovalRequest(pending) ─► notify approver ─► Approval Inbox (UI)
                                   approve ─► executor ─► service (human actor) ─► audit(approval_id)
                                   reject(+note) ─► agent revises (max 2) or stops
```

## 4. Approval matrix
| Action | Decision |
|---|---|
| Enrich fields (empty only, conf ≥0.8) | ALLOW, audited |
| Lead score/route; create Task/Notification; create Opportunity draft | ALLOW, visible |
| Quotation draft created by agent | ALLOW (status=draft) |
| Quotation → sent / any outbound email or WhatsApp | REQUIRE_APPROVAL (owner; discount tier escalates: >5% manager, >15% admin) |
| Order/Invoice creation from human-approved+accepted quote | ALLOW (rule-triggered) |
| Entity merge, delete, status rollback | REQUIRE_APPROVAL (always) |

## 5. Agents (build order: Enrich → Qualify → QuoteDesk → Monitor)
**Enrich** — autonomous, single Haiku call, no framework. Trigger: RQ job on Lead/Account create/update. Input: record + related activity text. Output Pydantic `{industry, size_band, job_title, …, confidence per field}`.
Rules: fill only *empty* fields; confidence ≥0.8 → write; else store in `ai_suggestions` for human. Normalization (phone, domain, casing) is deterministic code. Every field write audited.

**Qualify** — conversational, Sonnet, plain loop (no framework). `ChatSession(slots JSONB, status)`; slots: need/product, quantity, budget, timeline, authority. Per turn one call → `{reply, slot_updates, done}`;
one question at a time, ≤8 turns. Entity-resolve before creating the Lead. On done: deterministic BANT score → update Lead, create Opportunity draft, notify owner. `ChannelAdapter` interface (web widget first; WhatsApp = adapter only).

**QuoteDesk** — LangGraph + Postgres checkpointer + `interrupt`:
```
load_context (Context Pack) → parse_requirements (LLM → RequestedItem[text,qty,unit,needed_by])
 → match_products (semantic+trigram; ambiguous/low score = flagged, never guessed)
 → price_and_check (CODE: price, stock, MOQ, lead time, discount policy)
 → precedent (RAG over similar won quotes; advisory)
 → draft (service.create_quotation status=draft; totals by code)
 → explain (LLM: rationale + flags for reviewer)
 → policy_gate → interrupt(ApprovalRequest: review_quotation)
      approved → mark approved → (optional) draft customer email → gated send → END
      edited   → re-validate totals → continue
      rejected(feedback) → revise loop (max 2) → END
```
**Monitor** (stretch) — RQ scheduler every 15 min. Rules first: stalled deal (open opp, no activity ≥7d), quote expiring ≤3d, stock conflict (open quote qty > available), invoice overdue. Dedupe by `(rule, entity_id, day)`. Creates Task+Notification (ALLOW). LLM (Haiku) only writes the suggested next step.

## 6. Guardrails checklist (each agent PR must satisfy)
Allow-listed tools · Pydantic-validated args and outputs · policy check on every write · untrusted content delimited · no secrets/PII beyond need in prompts · iteration/time/token caps · idempotency key on retryable writes · run persisted with steps · scenario tests pass.

## 7. Evals & tests
`tests/agents/scenarios/*.yaml`: `{input, mocked_llm_responses, expected_effects}` — assert DB effects, approval requests and policy decisions, not prose. Include adversarial cases (prompt injection inside an email; discount above policy; ambiguous SKU; insufficient stock).
Live-LLM smoke tests: `@pytest.mark.llm`, opt-in. Temperature 0.

## 8. Observability
`agent_runs` (steps JSONB, tokens_in/out, cost_usd, latency, status) → UI "Agent Timeline" (demo asset).
