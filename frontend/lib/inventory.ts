import type { Product } from "@/lib/api/queries";

/** Available = on hand minus reserved for open orders, the same figure the stock check uses. */
export function available(product: Product): number {
  return Number(product.stock_qty) - Number(product.reserved_qty);
}
