# Discount policy

Applies to every quotation line. Enforced in code: `backend/app/modules/quotations/policy.py`.

## Approval tiers

A quotation's **largest line discount** decides who must approve it.

| Largest line discount | Who can approve | Status path                         |
|-----------------------|-----------------|--------------------------------------|
| 0% to 5%              | No approval needed (owner sends it) | draft → approved        |
| above 5% to 15%       | Manager or admin | draft → pending approval → approved |
| above 15%             | Admin only       | draft → pending approval → approved |

- A reviewer can also return a pending quotation to draft for edits.
- A rep cannot approve. Requests from a rep to approve above 5% get a 403.

## Rules

- Discounts are per line, from 0% to 100%. Prices and tax come from the catalog, never from the client.
- Discounts are applied before tax, and every amount is rounded half-up to the paisa.
- Changing an approved or sent quotation creates a new draft version. The new version is re-priced from current catalog prices and must go through the tiers again.
