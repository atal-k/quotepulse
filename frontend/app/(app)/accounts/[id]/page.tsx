"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge, statusTone } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { DataTable, type Column } from "@/components/data/data-table";
import { Fact, FactGrid } from "@/components/data/facts";
import { PageHeader } from "@/components/data/page-header";
import { Timeline } from "@/components/data/timeline";
import { ErrorState } from "@/components/ui/state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  type Contact,
  type Opportunity,
  type Quotation,
  useAccount,
  useAccountContacts,
  useAccountOpportunities,
  useAccountQuotations,
} from "@/lib/api/queries";
import { date, label, money } from "@/lib/format";

const CONTACT_COLUMNS: Column<Contact>[] = [
  {
    key: "name",
    header: "Name",
    cell: (c) => (
      <span className="block">
        <span className="block">
          {c.first_name} {c.last_name ?? ""}
        </span>
        <span className="block text-[13px] font-normal text-ink-muted">{c.job_title ?? "—"}</span>
      </span>
    ),
  },
  { key: "email", header: "Email", cell: (c) => <span className="text-ink-muted">{c.email ?? "—"}</span> },
  { key: "phone", header: "Phone", mono: true, cell: (c) => c.phone ?? "—" },
  { key: "primary", header: "", align: "right", cell: (c) => (c.is_primary ? <Badge tone="accent">Primary</Badge> : null) },
];

const OPPORTUNITY_COLUMNS: Column<Opportunity>[] = [
  { key: "name", header: "Opportunity", primary: true, cell: (o) => o.name },
  { key: "stage", header: "Stage", cell: (o) => <Badge tone={statusTone(o.stage)}>{label(o.stage)}</Badge> },
  { key: "amount", header: "Amount", align: "right", cell: (o) => money(o.amount) },
];

const QUOTATION_COLUMNS: Column<Quotation>[] = [
  { key: "number", header: "Quotation", mono: true, primary: true, cell: (q) => `${q.number} · v${q.version}` },
  { key: "status", header: "Status", cell: (q) => <Badge tone={statusTone(q.status)}>{label(q.status)}</Badge> },
  { key: "total", header: "Total", align: "right", cell: (q) => money(q.total) },
];

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const account = useAccount(id);
  const contacts = useAccountContacts(id);
  const opportunities = useAccountOpportunities(id);
  const quotations = useAccountQuotations(id);

  if (account.isError) {
    return (
      <>
        <BackLink />
        <Card className="mt-6">
          <ErrorState message={account.error.message} />
        </Card>
      </>
    );
  }

  if (account.isPending || !account.data) {
    return (
      <>
        <BackLink />
        <div className="mt-6 space-y-4">
          <Skeleton className="h-9 w-72" />
          <Skeleton className="h-24 w-full rounded-2xl" />
        </div>
      </>
    );
  }

  const a = account.data;
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow="Account"
        title={a.name}
        description={[a.domain, [a.city, a.state].filter(Boolean).join(", ")].filter(Boolean).join(" · ")}
        actions={<Badge tone={statusTone(a.status)}>{label(a.status)}</Badge>}
      />

      <FactGrid>
        <Fact label="GSTIN" mono>
          {a.tax_id ?? "—"}
        </Fact>
        <Fact label="Industry">{a.industry ?? "—"}</Fact>
        <Fact label="Payment terms">{a.payment_terms_days ? `${a.payment_terms_days} days` : "—"}</Fact>
        <Fact label="Credit limit" align="right">
          {money(a.credit_limit)}
        </Fact>
      </FactGrid>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <section aria-labelledby="contacts-h">
            <h2 id="contacts-h" className="mb-3 text-[15px] font-semibold tracking-tight text-ink">
              Contacts
            </h2>
            <DataTable
              columns={CONTACT_COLUMNS}
              rows={contacts.data?.items}
              rowKey={(c) => c.id}
              loading={contacts.isPending}
              error={contacts.error}
              emptyTitle="No contacts"
            />
          </section>

          <section aria-labelledby="opps-h">
            <h2 id="opps-h" className="mb-3 text-[15px] font-semibold tracking-tight text-ink">
              Opportunities
            </h2>
            <DataTable
              columns={OPPORTUNITY_COLUMNS}
              rows={opportunities.data?.items}
              rowKey={(o) => o.id}
              rowHref={(o) => `/opportunities/${o.id}`}
              loading={opportunities.isPending}
              error={opportunities.error}
              emptyTitle="No opportunities"
            />
          </section>

          <section aria-labelledby="quotes-h">
            <h2 id="quotes-h" className="mb-3 text-[15px] font-semibold tracking-tight text-ink">
              Quotations
            </h2>
            <DataTable
              columns={QUOTATION_COLUMNS}
              rows={quotations.data?.items}
              rowKey={(q) => q.id}
              rowHref={(q) => `/quotations/${q.id}`}
              loading={quotations.isPending}
              error={quotations.error}
              emptyTitle="No quotations"
            />
          </section>
        </div>

        <div className="lg:sticky lg:top-8 lg:self-start">
          <Timeline entityType="account" entityId={a.id} />
        </div>
      </div>
      <p className="mt-8 text-[12px] text-ink-faint">Created {date(a.created_at)}</p>
    </>
  );
}

function BackLink() {
  return (
    <Link
      href="/accounts"
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      Accounts
    </Link>
  );
}
