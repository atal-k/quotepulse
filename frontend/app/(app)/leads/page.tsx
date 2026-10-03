"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { Badge, statusTone } from "@/components/ui/badge";
import { SegmentedControl, type SegmentOption } from "@/components/ui/segmented";
import { PAGE_SIZE, type Lead, useLeads } from "@/lib/api/queries";
import { label } from "@/lib/format";

type LeadStatus = Lead["status"];

const FILTERS: SegmentOption<LeadStatus>[] = [
  { value: "", label: "All" },
  { value: "new", label: "New" },
  { value: "contacted", label: "Contacted" },
  { value: "qualified", label: "Qualified" },
  { value: "converted", label: "Converted" },
  { value: "disqualified", label: "Disqualified" },
];

const COLUMNS: Column<Lead>[] = [
  {
    key: "name",
    header: "Lead",
    primary: true,
    cell: (l) => (
      <span className="block">
        <span className="block">{l.name}</span>
        <span className="block text-[13px] font-normal text-ink-muted">{l.company_name ?? "—"}</span>
      </span>
    ),
  },
  { key: "status", header: "Status", cell: (l) => <Badge tone={statusTone(l.status)}>{label(l.status)}</Badge> },
  { key: "source", header: "Source", cell: (l) => <span className="text-ink-muted">{label(l.source)}</span> },
  { key: "score", header: "Score", align: "right", cell: (l) => (l.score === null ? "—" : `${l.score}`) },
];

export default function LeadsPage() {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState<LeadStatus | "">("");
  const query = useLeads({ limit: PAGE_SIZE, offset }, status || undefined);

  function changeStatus(next: LeadStatus | "") {
    setStatus(next);
    setOffset(0);
  }

  return (
    <>
      <PageHeader
        eyebrow="Pipeline"
        title="Leads"
        description={query.data ? `${query.data.total} leads${status ? ` · ${label(status).toLowerCase()}` : ""}` : "Loading leads"}
        actions={<SegmentedControl label="Filter by status" options={FILTERS} value={status} onChange={changeStatus} />}
      />
      <DataTable
        columns={COLUMNS}
        rows={query.data?.items}
        rowKey={(l) => l.id}
        rowHref={(l) => `/leads/${l.id}`}
        loading={query.isPending}
        error={query.error}
        emptyTitle="No leads match this filter"
        emptyHint="Try another status, or add leads from the API while we build the create flow."
        footer={<Pagination page={query.data} offset={offset} onOffset={setOffset} />}
      />
    </>
  );
}
