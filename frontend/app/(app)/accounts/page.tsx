"use client";

import { useState } from "react";

import { Badge, statusTone } from "@/components/ui/badge";
import { DataTable, type Column } from "@/components/data/data-table";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { PAGE_SIZE, type Account, useAccounts } from "@/lib/api/queries";
import { label, money } from "@/lib/format";

const COLUMNS: Column<Account>[] = [
  {
    key: "name",
    header: "Account",
    primary: true,
    cell: (a) => (
      <span className="block">
        <span className="block">{a.name}</span>
        <span className="block text-[13px] font-normal text-ink-muted">
          {[a.city, a.state].filter(Boolean).join(", ") || "—"}
        </span>
      </span>
    ),
  },
  { key: "gst", header: "GSTIN", mono: true, cell: (a) => a.tax_id ?? "—" },
  { key: "industry", header: "Industry", cell: (a) => a.industry ?? "—" },
  { key: "status", header: "Status", cell: (a) => <Badge tone={statusTone(a.status)}>{label(a.status)}</Badge> },
  {
    key: "terms",
    header: "Terms",
    align: "right",
    cell: (a) => (a.payment_terms_days ? `${a.payment_terms_days} days` : "—"),
  },
  { key: "credit", header: "Credit limit", align: "right", cell: (a) => money(a.credit_limit) },
];

export default function AccountsPage() {
  const [offset, setOffset] = useState(0);
  const query = useAccounts({ limit: PAGE_SIZE, offset });

  return (
    <>
      <PageHeader
        eyebrow="Customers"
        title="Accounts"
        description={query.data ? `${query.data.total} accounts you can see` : "Loading your accounts"}
      />
      <DataTable
        columns={COLUMNS}
        rows={query.data?.items}
        rowKey={(a) => a.id}
        rowHref={(a) => `/accounts/${a.id}`}
        loading={query.isPending}
        error={query.error}
        emptyTitle="No accounts yet"
        emptyHint="Accounts appear here once a lead is converted or one is created."
        footer={<Pagination page={query.data} offset={offset} onOffset={setOffset} />}
      />
    </>
  );
}
