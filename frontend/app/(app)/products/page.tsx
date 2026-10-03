"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { Badge } from "@/components/ui/badge";
import { PAGE_SIZE, type Product, useProducts } from "@/lib/api/queries";
import { available } from "@/lib/inventory";
import { label, money } from "@/lib/format";

const COLUMNS: Column<Product>[] = [
  { key: "sku", header: "SKU", mono: true, primary: true, cell: (p) => p.sku },
  {
    key: "name",
    header: "Product",
    cell: (p) => (
      <span className="block">
        <span className="block">{p.name}</span>
        <span className="block text-[13px] font-normal text-ink-muted">{label(p.category)}</span>
      </span>
    ),
  },
  { key: "price", header: "Unit price", align: "right", cell: (p) => money(p.unit_price) },
  { key: "gst", header: "GST", align: "right", cell: (p) => `${p.tax_pct}%` },
  {
    key: "available",
    header: "Available",
    align: "right",
    cell: (p) => {
      const qty = available(p);
      const low = qty <= Number(p.reorder_level);
      return (
        <span className={low ? "text-warning" : undefined}>
          {qty.toLocaleString("en-IN")} {p.unit}
        </span>
      );
    },
  },
];

export default function ProductsPage() {
  const [offset, setOffset] = useState(0);
  const query = useProducts({ limit: PAGE_SIZE, offset });

  return (
    <>
      <PageHeader
        eyebrow="Catalog"
        title="Products"
        description={query.data ? `${query.data.total} products in the catalog` : "Loading catalog"}
      />
      <DataTable
        columns={COLUMNS}
        rows={query.data?.items}
        rowKey={(p) => p.id}
        rowHref={(p) => `/products/${p.id}`}
        loading={query.isPending}
        error={query.error}
        emptyTitle="The catalog is empty"
        emptyHint="Products are added by an administrator."
        footer={<Pagination page={query.data} offset={offset} onOffset={setOffset} />}
      />
      <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-faint">
        <Badge tone="warning">Low</Badge>
        Available stock at or below the reorder level.
      </p>
    </>
  );
}
