"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { Badge, statusTone } from "@/components/ui/badge";
import { SegmentedControl, type SegmentOption } from "@/components/ui/segmented";
import { PAGE_SIZE, type Invoice, useInvoices } from "@/lib/api/queries";
import { date, label, money } from "@/lib/format";

const FILTERS: SegmentOption<string>[] = [
  { value: "", label: "All" },
  { value: "issued", label: "Issued" },
  { value: "partially_paid", label: "Part paid" },
  { value: "paid", label: "Paid" },
  { value: "void", label: "Void" },
];

const COLUMNS: Column<Invoice>[] = [
  {
    key: "number",
    header: "Invoice",
    mono: true,
    primary: true,
    cell: (i) => (
      <span className="block">
        <span className="block">{i.number}</span>
        <span className="block font-sans text-[13px] font-normal text-ink-muted">Issued {date(i.issue_date)}</span>
      </span>
    ),
  },
  {
    key: "status",
    header: "Status",
    cell: (i) => (
      <span className="flex items-center gap-2">
        <Badge tone={statusTone(i.status)}>{label(i.status)}</Badge>
        {i.overdue ? <Badge tone="danger">Overdue</Badge> : null}
      </span>
    ),
  },
  { key: "due", header: "Due", cell: (i) => <span className="text-ink-muted">{date(i.due_date)}</span> },
  { key: "total", header: "Total", align: "right", cell: (i) => money(i.total) },
];

export default function InvoicesPage() {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const query = useInvoices({ limit: PAGE_SIZE, offset }, status || undefined);

  function changeStatus(next: string) {
    setStatus(next);
    setOffset(0);
  }

  return (
    <>
      <PageHeader
        eyebrow="Billing"
        title="Invoices"
        description={query.data ? `${query.data.total} invoices${status ? ` · ${label(status).toLowerCase()}` : ""}` : "Loading invoices"}
        actions={<SegmentedControl label="Filter by status" options={FILTERS} value={status} onChange={changeStatus} />}
      />
      <DataTable
        columns={COLUMNS}
        rows={query.data?.items}
        rowKey={(i) => i.id}
        rowHref={(i) => `/invoices/${i.id}`}
        loading={query.isPending}
        error={query.error}
        emptyTitle="No invoices in this status"
        emptyHint="Invoices are issued when their order ships."
        footer={<Pagination page={query.data} offset={offset} onOffset={setOffset} />}
      />
    </>
  );
}
