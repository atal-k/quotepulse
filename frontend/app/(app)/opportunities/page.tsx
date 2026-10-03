"use client";

import { useState } from "react";

import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { Badge, statusTone } from "@/components/ui/badge";
import { SegmentedControl, type SegmentOption } from "@/components/ui/segmented";
import { PAGE_SIZE, type Opportunity, useOpportunities } from "@/lib/api/queries";
import { date, label, money } from "@/lib/format";

type Stage = Opportunity["stage"];

const FILTERS: SegmentOption<Stage>[] = [
  { value: "", label: "All" },
  { value: "discovery", label: "Discovery" },
  { value: "proposal", label: "Proposal" },
  { value: "negotiation", label: "Negotiation" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

const COLUMNS: Column<Opportunity>[] = [
  { key: "name", header: "Opportunity", primary: true, cell: (o) => o.name },
  { key: "stage", header: "Stage", cell: (o) => <Badge tone={statusTone(o.stage)}>{label(o.stage)}</Badge> },
  {
    key: "probability",
    header: "Probability",
    align: "right",
    cell: (o) => (o.probability === null ? "—" : `${o.probability}%`),
  },
  { key: "close", header: "Expected close", cell: (o) => <span className="text-ink-muted">{date(o.expected_close_date)}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (o) => money(o.amount) },
];

export default function OpportunitiesPage() {
  const [offset, setOffset] = useState(0);
  const [stage, setStage] = useState<Stage | "">("");
  const query = useOpportunities({ limit: PAGE_SIZE, offset }, stage || undefined);

  function changeStage(next: Stage | "") {
    setStage(next);
    setOffset(0);
  }

  return (
    <>
      <PageHeader
        eyebrow="Pipeline"
        title="Opportunities"
        description={query.data ? `${query.data.total} deals${stage ? ` in ${label(stage).toLowerCase()}` : ""}` : "Loading deals"}
        actions={<SegmentedControl label="Filter by stage" options={FILTERS} value={stage} onChange={changeStage} />}
      />
      <DataTable
        columns={COLUMNS}
        rows={query.data?.items}
        rowKey={(o) => o.id}
        rowHref={(o) => `/opportunities/${o.id}`}
        loading={query.isPending}
        error={query.error}
        emptyTitle="No deals in this stage"
        emptyHint="Opportunities appear as leads are qualified or accounts start buying."
        footer={<Pagination page={query.data} offset={offset} onOffset={setOffset} />}
      />
    </>
  );
}
