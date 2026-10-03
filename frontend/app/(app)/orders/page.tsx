"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { Badge, statusTone } from "@/components/ui/badge";
import { SegmentedControl, type SegmentOption } from "@/components/ui/segmented";
import { PAGE_SIZE, type Order, useOrders } from "@/lib/api/queries";
import { date, label, money } from "@/lib/format";

const FILTERS: SegmentOption<string>[] = [
  { value: "", label: "All" },
  { value: "confirmed", label: "Confirmed" },
  { value: "processing", label: "Processing" },
  { value: "shipped", label: "Shipped" },
  { value: "delivered", label: "Delivered" },
];

const COLUMNS: Column<Order>[] = [
  { key: "number", header: "Order", mono: true, primary: true, cell: (o) => o.number },
  { key: "status", header: "Status", cell: (o) => <Badge tone={statusTone(o.status)}>{label(o.status)}</Badge> },
  { key: "delivery", header: "Expected delivery", cell: (o) => <span className="text-ink-muted">{date(o.expected_delivery_date)}</span> },
  { key: "total", header: "Total", align: "right", cell: (o) => money(o.total) },
];

export default function OrdersPage() {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const query = useOrders({ limit: PAGE_SIZE, offset }, status || undefined);

  function changeStatus(next: string) {
    setStatus(next);
    setOffset(0);
  }

  return (
    <>
      <PageHeader
        eyebrow="Sales"
        title="Orders"
        description={query.data ? `${query.data.total} orders${status ? ` · ${label(status).toLowerCase()}` : ""}` : "Loading orders"}
        actions={<SegmentedControl label="Filter by status" options={FILTERS} value={status} onChange={changeStatus} />}
      />
      <DataTable
        columns={COLUMNS}
        rows={query.data?.items}
        rowKey={(o) => o.id}
        rowHref={(o) => `/orders/${o.id}`}
        loading={query.isPending}
        error={query.error}
        emptyTitle="No orders in this status"
        emptyHint="Orders are created when a customer accepts a quotation."
        footer={<Pagination page={query.data} offset={offset} onOffset={setOffset} />}
      />
    </>
  );
}
