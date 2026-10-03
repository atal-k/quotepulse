# Payment-terms policy

Enforced in code: `backend/app/modules/invoices/service.py` (`DEFAULT_PAYMENT_TERMS_DAYS`).

## Due date

- An invoice is issued when its order ships. Its issue date is that day.
- Due date = issue date + the account's **payment terms in days**.
- If the account has no payment terms set, the default is **30 days**.

## Payments

- A payment is recorded against an issued or partially paid invoice. It must be greater than zero.
- Payments accumulate. The invoice becomes **partially paid** after a part payment and **paid** when the total is reached.
- Overpayment is rejected. The outstanding balance is returned in the error.
- Paying an invoice that is already paid is rejected.

## Voiding

- Only an issued invoice with no payments can be voided.

## Overdue

- An issued or partially paid invoice is **overdue** once today is after its due date.
- Overdue is derived from the due date when read. It is not stored.
