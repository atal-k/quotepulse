import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, errorMessage } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

// Every type here is taken from the generated OpenAPI schema; nothing is hand-written.
export type Account = components["schemas"]["AccountRead"];
export type Contact = components["schemas"]["ContactRead"];
export type Lead = components["schemas"]["LeadRead"];
export type Opportunity = components["schemas"]["OpportunityRead"];
export type Quotation = components["schemas"]["QuotationRead"];
export type QuotationItem = components["schemas"]["QuotationItemRead"];
export type Activity = components["schemas"]["ActivityRead"];
export type Order = components["schemas"]["OrderRead"];
export type OrderItem = components["schemas"]["OrderItemRead"];
export type Invoice = components["schemas"]["InvoiceRead"];
export type Product = components["schemas"]["ProductRead"];

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface PageRequest {
  limit: number;
  offset: number;
}

export const PAGE_SIZE = 20;

/** Turns an openapi-fetch result into its data, or throws the backend's error message. */
export async function unwrap<T>(call: Promise<{ data?: T; error?: unknown }>): Promise<T> {
  const { data, error } = await call;
  if (error !== undefined || data === undefined) {
    throw new Error(errorMessage(error));
  }
  return data;
}

function listQuery<T>(key: string, fetcher: (page: PageRequest) => Promise<Page<T>>) {
  return (page: PageRequest) =>
    useQuery({
      queryKey: [key, page],
      queryFn: () => fetcher(page),
      placeholderData: keepPreviousData,
    });
}

// ---- accounts -------------------------------------------------------------------------------

export const useAccounts = listQuery<Account>("accounts", (page) =>
  unwrap(api.GET("/api/v1/accounts", { params: { query: page } })),
);

export function useAccount(id: string) {
  return useQuery({
    queryKey: ["account", id],
    enabled: Boolean(id),
    queryFn: () => unwrap(api.GET("/api/v1/accounts/{account_id}", { params: { path: { account_id: id } } })),
  });
}

export function useAccountContacts(accountId: string) {
  return useQuery({
    queryKey: ["contacts", "account", accountId],
    enabled: Boolean(accountId),
    queryFn: () =>
      unwrap(api.GET("/api/v1/contacts", { params: { query: { account_id: accountId, limit: 100, offset: 0 } } })),
  });
}

export function useAccountOpportunities(accountId: string) {
  return useQuery({
    queryKey: ["opportunities", "account", accountId],
    enabled: Boolean(accountId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/opportunities", { params: { query: { account_id: accountId, limit: 100, offset: 0 } } }),
      ),
  });
}

export function useAccountQuotations(accountId: string) {
  return useQuery({
    queryKey: ["quotations", "account", accountId],
    enabled: Boolean(accountId),
    queryFn: () =>
      unwrap(api.GET("/api/v1/quotations", { params: { query: { account_id: accountId, limit: 100, offset: 0 } } })),
  });
}

// ---- leads ----------------------------------------------------------------------------------

export function useLeads(page: PageRequest, status?: Lead["status"]) {
  return useQuery({
    queryKey: ["leads", page, status ?? null],
    queryFn: () => unwrap(api.GET("/api/v1/leads", { params: { query: { ...page, status } } })),
    placeholderData: keepPreviousData,
  });
}

export function useLead(id: string) {
  return useQuery({
    queryKey: ["lead", id],
    enabled: Boolean(id),
    queryFn: () => unwrap(api.GET("/api/v1/leads/{lead_id}", { params: { path: { lead_id: id } } })),
  });
}

// ---- opportunities --------------------------------------------------------------------------

export function useOpportunities(page: PageRequest, stage?: Opportunity["stage"]) {
  return useQuery({
    queryKey: ["opportunities", page, stage ?? null],
    queryFn: () => unwrap(api.GET("/api/v1/opportunities", { params: { query: { ...page, stage } } })),
    placeholderData: keepPreviousData,
  });
}

export function useOpportunity(id: string) {
  return useQuery({
    queryKey: ["opportunity", id],
    enabled: Boolean(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/opportunities/{opportunity_id}", { params: { path: { opportunity_id: id } } })),
  });
}

// ---- quotations -----------------------------------------------------------------------------

export function useQuotations(page: PageRequest, status?: string) {
  return useQuery({
    queryKey: ["quotations", page, status ?? null],
    queryFn: () => unwrap(api.GET("/api/v1/quotations", { params: { query: { ...page, status } } })),
    placeholderData: keepPreviousData,
  });
}

export function useQuotation(id: string) {
  return useQuery({
    queryKey: ["quotation", id],
    enabled: Boolean(id),
    queryFn: () => unwrap(api.GET("/api/v1/quotations/{quotation_id}", { params: { path: { quotation_id: id } } })),
  });
}

// ---- activities (the timeline shown on every detail page) -----------------------------------

export function useTimeline(entityType: Activity["entity_type"], entityId: string) {
  return useQuery({
    queryKey: ["activities", entityType, entityId],
    enabled: Boolean(entityId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/activities", {
          params: { query: { entity_type: entityType, entity_id: entityId, limit: 50, offset: 0 } },
        }),
      ),
  });
}

// ---- orders ---------------------------------------------------------------------------------

export function useOrders(page: PageRequest, status?: string) {
  return useQuery({
    queryKey: ["orders", page, status ?? null],
    queryFn: () => unwrap(api.GET("/api/v1/orders", { params: { query: { ...page, status } } })),
    placeholderData: keepPreviousData,
  });
}

export function useOrder(id: string) {
  return useQuery({
    queryKey: ["order", id],
    enabled: Boolean(id),
    queryFn: () => unwrap(api.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })),
  });
}

// ---- invoices -------------------------------------------------------------------------------

export function useInvoices(page: PageRequest, status?: string) {
  return useQuery({
    queryKey: ["invoices", page, status ?? null],
    queryFn: () => unwrap(api.GET("/api/v1/invoices", { params: { query: { ...page, status } } })),
    placeholderData: keepPreviousData,
  });
}

export function useInvoice(id: string) {
  return useQuery({
    queryKey: ["invoice", id],
    enabled: Boolean(id),
    queryFn: () => unwrap(api.GET("/api/v1/invoices/{invoice_id}", { params: { path: { invoice_id: id } } })),
  });
}

// ---- products -------------------------------------------------------------------------------

export function useProducts(page: PageRequest) {
  return useQuery({
    queryKey: ["products", page],
    queryFn: () => unwrap(api.GET("/api/v1/products", { params: { query: page } })),
    placeholderData: keepPreviousData,
  });
}

export function useProduct(id: string) {
  return useQuery({
    queryKey: ["product", id],
    enabled: Boolean(id),
    queryFn: () => unwrap(api.GET("/api/v1/products/{product_id}", { params: { path: { product_id: id } } })),
  });
}

// ---- current user ---------------------------------------------------------------------------

export function useMe(enabled = true) {
  return useQuery({
    queryKey: ["me"],
    enabled,
    queryFn: () => unwrap(api.GET("/api/v1/me")),
    staleTime: 5 * 60_000,
  });
}
