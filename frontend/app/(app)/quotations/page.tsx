"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { Badge, statusTone } from "@/components/ui/badge";
import { SegmentedControl, type SegmentOption } from "@/components/ui/segmented";
import { PAGE_SIZE, type Quotation, useQuotations } from "@/lib/api/queries";
import { date, label, money } from "@/lib/format";

const FILTERS: SegmentOption<string>[] = [
  { value: "", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "pending_approval", label: "Pending approval" },
  { value: "approved", label: "Approved" },
  { value: "sent", label: "Sent" },
  { value: "accepted", label: "Accepted" },
];

const COLUMNS: Column<Quotation>[] = [
  {
    key: "number",
    header: "Quotation",
    mono: true,
    primary: true,
    cell: (q) => (
      <span className="block">
        <span className="block">{q.number}</span>
        <span className="block font-sans text-[13px] font-normal text-ink-muted">Version {q.version}</span>
      </span>
    ),
  },
  { key: "status", header: "Status", cell: (q) => <Badge tone={statusTone(q.status)}>{label(q.status)}</Badge> },
  {
    key: "approval",
    header: "Approval",
    cell: (q) =>
      q.status === "pending_approval" && q.approver_role ? (
        <span className="text-[13px] text-warning">Needs {label(q.approver_role).toLowerCase()}</span>
      ) : (
        <span className="text-ink-faint">—</span>
      ),
  },
  { key: "valid", header: "Valid until", cell: (q) => <span className="text-ink-muted">{date(q.valid_until)}</span> },
  { key: "total", header: "Total", align: "right", cell: (q) => money(q.total) },
];

export default function QuotationsPage() {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const query = useQuotations({ limit: PAGE_SIZE, offset }, status || undefined);

  function changeStatus(next: string) {
    setStatus(next);
    setOffset(0);
  }

  return (
    <>
      <PageHeader
        eyebrow="Sales"
        title="Quotations"
        description={query.data ? `${query.data.total} quotations${status ? ` · ${label(status).toLowerCase()}` : ""}` : "Loading quotations"}
        actions={<SegmentedControl label="Filter by status" options={FILTERS} value={status} onChange={changeStatus} />}
      />
      <DataTable
        columns={COLUMNS}
        rows={query.data?.items}
        rowKey={(q) => q.id}
        rowHref={(q) => `/quotations/${q.id}`}
        loading={query.isPending}
        error={query.error}
        emptyTitle="No quotations in this status"
        emptyHint="Quotations appear here once they are drafted against an account."
        footer={<Pagination page={query.data} offset={offset} onOffset={setOffset} />}
      />
    </>
  );
}
