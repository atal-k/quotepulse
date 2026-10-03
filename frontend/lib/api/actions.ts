import { api } from "@/lib/api/client";
import { unwrap, type Invoice, type Order, type Quotation } from "@/lib/api/queries";

// Raw calls to the existing state-transition endpoints. Every screen and the Phase 4 Approval Inbox
// go through these, so there is exactly one place per transition.

export type QuotationAction = "submit" | "approve" | "send" | "accept";

export const quotationActions: Record<QuotationAction, (id: string) => Promise<Quotation>> = {
  submit: (id) =>
    unwrap(api.POST("/api/v1/quotations/{quotation_id}/submit", { params: { path: { quotation_id: id } } })),
  approve: (id) =>
    unwrap(api.POST("/api/v1/quotations/{quotation_id}/approve", { params: { path: { quotation_id: id } } })),
  send: (id) => unwrap(api.POST("/api/v1/quotations/{quotation_id}/send", { params: { path: { quotation_id: id } } })),
  accept: (id) =>
    unwrap(api.POST("/api/v1/quotations/{quotation_id}/accept", { params: { path: { quotation_id: id } } })),
};

export function processOrder(id: string): Promise<Order> {
  return unwrap(api.POST("/api/v1/orders/{order_id}/process", { params: { path: { order_id: id } } }));
}

export function deliverOrder(id: string): Promise<Order> {
  return unwrap(api.POST("/api/v1/orders/{order_id}/deliver", { params: { path: { order_id: id } } }));
}

export function shipOrder(id: string): Promise<Order> {
  return unwrap(api.POST("/api/v1/orders/{order_id}/ship", { params: { path: { order_id: id } } }));
}

export function recordPayment(id: string, amount: string): Promise<Invoice> {
  return unwrap(
    api.POST("/api/v1/invoices/{invoice_id}/payments", {
      params: { path: { invoice_id: id } },
      body: { amount },
    }),
  );
}

/** Mirrors the backend's approval tiers (quotations/policy.py) for display only: the server is the
 * authority and will refuse an unauthorised approval regardless of what the UI shows. */
export function canApprove(role: string | undefined, required: string | null | undefined): boolean {
  if (!required) return true;
  if (required === "manager") return role === "manager" || role === "admin";
  return role === "admin";
}
