"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DataTable, type Column } from "@/components/data/data-table";
import { Fact, FactGrid } from "@/components/data/facts";
import { PageHeader } from "@/components/data/page-header";
import { Timeline } from "@/components/data/timeline";
import { Badge, statusTone } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/state";
import { type Quotation, useAccount, useAccountQuotations, useOpportunity } from "@/lib/api/queries";
import { date, label, money } from "@/lib/format";

const QUOTATION_COLUMNS: Column<Quotation>[] = [
  { key: "number", header: "Quotation", mono: true, primary: true, cell: (q) => `${q.number} · v${q.version}` },
  { key: "status", header: "Status", cell: (q) => <Badge tone={statusTone(q.status)}>{label(q.status)}</Badge> },
  { key: "total", header: "Total", align: "right", cell: (q) => money(q.total) },
];

export default function OpportunityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const opportunity = useOpportunity(id);
  const accountId = opportunity.data?.account_id ?? "";
  const account = useAccount(accountId);
  const quotations = useAccountQuotations(accountId);

  if (opportunity.isError) {
    return (
      <>
        <BackLink />
        <Card className="mt-6">
          <ErrorState message={opportunity.error.message} />
        </Card>
      </>
    );
  }

  if (opportunity.isPending || !opportunity.data) {
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

  const o = opportunity.data;
  // The quotation list is scoped to the account; keep the ones written against this deal.
  const linked = quotations.data?.items.filter((q) => q.opportunity_id === o.id);
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow="Opportunity"
        title={o.name}
        description={
          account.data ? (
            <Link href={`/accounts/${account.data.id}`} className="hover:text-accent-strong hover:underline">
              {account.data.name}
            </Link>
          ) : (
            "Loading account"
          )
        }
        actions={<Badge tone={statusTone(o.stage)}>{label(o.stage)}</Badge>}
      />

      <FactGrid>
        <Fact label="Amount">{money(o.amount)}</Fact>
        <Fact label="Probability">{o.probability === null ? "—" : `${o.probability}%`}</Fact>
        <Fact label="Expected close">{date(o.expected_close_date)}</Fact>
        <Fact label="Closed" align="right">
          {o.closed_at ? date(o.closed_at) : "Open"}
        </Fact>
      </FactGrid>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Card className="animate-fade-up">
            <CardHeader>
              <CardTitle>Requirements</CardTitle>
            </CardHeader>
            <p className="px-6 pb-6 pt-4 text-[14px] leading-relaxed text-ink">
              {o.requirements ?? "No requirements recorded yet."}
            </p>
            {o.lost_reason ? (
              <p className="border-t border-line-soft px-6 py-4 text-[13px] text-danger">Lost: {o.lost_reason}</p>
            ) : null}
          </Card>

          <section aria-labelledby="linked-quotes">
            <h2 id="linked-quotes" className="mb-3 text-[15px] font-semibold tracking-tight text-ink">
              Quotations
            </h2>
            <DataTable
              columns={QUOTATION_COLUMNS}
              rows={linked}
              rowKey={(q) => q.id}
              rowHref={(q) => `/quotations/${q.id}`}
              loading={quotations.isPending}
              error={quotations.error}
              emptyTitle="No quotations for this deal yet"
            />
          </section>
        </div>

        <div className="lg:sticky lg:top-8 lg:self-start">
          <Timeline entityType="opportunity" entityId={o.id} />
        </div>
      </div>
    </>
  );
}

function BackLink() {
  return (
    <Link
      href="/opportunities"
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      Opportunities
    </Link>
  );
}
