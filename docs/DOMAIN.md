# DOMAIN — Industrial supplies distributor (synthetic B2B, India)

## Tables (Phase 1)
`teams, users, accounts, contacts, leads, opportunities, activities, tasks, products, quotations, quotation_items, orders, order_items, invoices, notifications, audit_logs, document_sequences`
Later: `approval_requests, agent_runs, chat_sessions/chat_messages, kb_documents/kb_chunks, personal_access_tokens`.

| Object | Key fields |
|---|---|
| User | email(unique,lower), full_name, hashed_password, role(admin/manager/rep), team_id, is_active |
| Account | name, domain(unique,lower), industry, tax_id(GSTIN), city/state/country, status(prospect/customer/inactive), credit_limit, payment_terms_days, owner/team |
| Contact | account_id, first/last name, email, phone, job_title, is_primary, owner/team |
| Lead | name, company_name, email, phone, source, status, score, qualification(JSONB BANT), converted_account_id/contact_id, owner/team |
| Opportunity | account_id, contact_id?, lead_id?, name, stage, amount, currency, probability, expected_close_date, requirements(text), lost_reason, closed_at |
| Product | sku(unique), name, category, unit, unit_price, currency, tax_pct, stock_qty, reserved_qty, reorder_level, min_order_qty, lead_time_days, is_active. Checks: qty ≥ 0 |
| Quotation / Item | number, account, opportunity, status, version, valid_until, subtotal, discount_total, tax_total, total, terms, created_by_kind / product, description, qty>0, unit_price, discount_pct 0-100, tax_pct, line_total |
| Order / Item | number, quotation_id(unique), account, status, totals, shipping_address, expected_delivery_date / product, qty, unit_price, tax, line_total |
| Invoice | number, order, account, status, issue_date, due_date, total, amount_paid |
| Activity | type(call/email/meeting/note/chat/whatsapp), direction, subject, body, occurred_at, entity_type+entity_id, created_by_kind, meta JSONB, embedding (P2). Index (entity_type, entity_id, occurred_at) |
| Task / Notification | title, due_at, status, priority, owner=assignee, entity ref / user_id, kind, title, read_at |

Owned rows (`owner_id`, `team_id`): account, contact, lead, opportunity, activity, task, quotation, order, invoice. Catalog is global (admin-managed).

## State machines (enforce with a `TRANSITIONS` table in code; invalid → `Conflict`)
- **Lead:** new → contacted → qualified → converted; any → disqualified. Convert = create Account(+Contact)+Opportunity in one transaction, store links.
- **Opportunity:** discovery → proposal → negotiation → won | lost (lost needs `lost_reason`). `won` is set automatically when a quotation is accepted.
- **Quotation:** draft → pending_approval → approved → sent → accepted | rejected | expired; pending_approval → draft on reviewer rejection. Editable only in `draft`; changes after approval create a new version. Accepted → auto-create Order + mark Opportunity won.
- **Order:** confirmed → processing → shipped → delivered; confirmed/processing → cancelled.
- **Invoice:** draft → issued → partially_paid → paid; issued → overdue (derived by Monitor); unpaid → void. Issued when order ships; `due_date = issue_date + account.payment_terms_days`.

## Business rules (deterministic code, unit-tested)
- **Totals (server only):** `net = qty×unit_price×(1−disc/100)`; `tax = net×tax_pct/100`; round each line `ROUND_HALF_UP` to 2 dp; `subtotal=Σnet`, `discount_total=Σ(qty×price×disc%)`, `tax_total=Σtax`, `total=subtotal+tax_total`. Client/LLM values are ignored.
- **Discount approval:** ≤5% owner · >5–15% manager · >15% admin (thresholds in settings). Agent-drafted quotes always need human review before sending.
- **Stock:** `available = stock_qty − reserved_qty`. Quote draft: advisory check. Order creation: reserve atomically (`SELECT … FOR UPDATE` products ordered by id) → `Conflict(insufficient_stock, per-SKU details)` if short. Shipped: `stock_qty−=qty`, `reserved_qty−=qty`. Cancelled: release reservation. MOQ and lead time surfaced in checks.
- **Numbering:** `document_sequences(kind, year, last_value)` with row lock → `QT-2026-00001`, `SO-…`, `INV-…`.
