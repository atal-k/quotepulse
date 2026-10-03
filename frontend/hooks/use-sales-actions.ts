"use client";

import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";

import {
  deliverOrder,
  processOrder,
  quotationActions,
  recordPayment,
  shipOrder,
  type QuotationAction,
} from "@/lib/api/actions";

/** Every sales read that a transition can change. Invalidated together so no list goes stale. */
export function invalidateSales(client: QueryClient): Promise<void> {
  return Promise.all(
    ["quotation", "quotations", "order", "orders", "invoice", "invoices", "opportunity", "opportunities"].map(
      (key) => client.invalidateQueries({ queryKey: [key] }),
    ),
  ).then(() => undefined);
}

/** A quotation transition as a mutation. Pages and the Approval Inbox both use this. */
export function useQuotationAction(id: string, action: QuotationAction) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => quotationActions[action](id),
    onSuccess: () => invalidateSales(client),
  });
}

/** Approving is the action the Phase 4 Approval Inbox will also use, so it has its own name. */
export function useApproveQuotation(id: string) {
  return useQuotationAction(id, "approve");
}

export function useProcessOrder(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => processOrder(id),
    onSuccess: () => invalidateSales(client),
  });
}

export function useDeliverOrder(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => deliverOrder(id),
    onSuccess: () => invalidateSales(client),
  });
}

export function useShipOrder(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => shipOrder(id),
    onSuccess: () => invalidateSales(client),
  });
}

export function useRecordPayment(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (amount: string) => recordPayment(id, amount),
    onSuccess: () => invalidateSales(client),
  });
}
