"use client";

import { ArrowLeft, Clock } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DataTable, type Column } from "@/components/data/data-table";
import { Fact, FactGrid } from "@/components/data/facts";
import { PageHeader } from "@/components/data/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/state";
import { QuotationActions } from "@/components/sales/quotation-actions";
import { type QuotationItem, useAccount, useQuotation } from "@/lib/api/queries";
import { date, label, money } from "@/lib/format";

const LINE_COLUMNS: Column<QuotationItem>[] = [
  {
    key: "description",
    header: "Item",
    cell: (i) => (
      <span className="block">
        <span className="block text-ink">{i.description}</span>
        <span className="block font-mono text-[12px] text-ink-faint">Line {i.position}</span>
      </span>
    ),
  },
  { key: "qty", header: "Qty", align: "right", cell: (i) => Number(i.qty).toLocaleString("en-IN") },
  { key: "price", header: "Unit price", align: "right", cell: (i) => money(i.unit_price) },
  {
    key: "disc",
    header: "Discount",
    align: "right",
    cell: (i) => (Number(i.discount_pct) > 0 ? <span className="text-warning">{i.discount_pct}%</span> : "—"),
  },
  { key: "tax", header: "GST", align: "right", cell: (i) => `${i.tax_pct}%` },
  { key: "total", header: "Line total", align: "right", cell: (i) => <span className="font-medium">{money(i.line_total)}</span> },
];

export default function QuotationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const quotation = useQuotation(id);
  const account = useAccount(quotation.data?.account_id ?? "");

  if (quotation.isError) {
    return (
      <>
        <BackLink />
        <Card className="mt-6">
          <ErrorState message={quotation.error.message} />
        </Card>
      </>
    );
  }

  if (quotation.isPending || !quotation.data) {
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

  const q = quotation.data;
  const awaitingApproval = q.status === "pending_approval";
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Quotation · version ${q.version}`}
        title={<span className="font-mono">{q.number}</span>}
        description={
          account.data ? (
            <Link href={`/accounts/${account.data.id}`} className="hover:text-accent-strong hover:underline">
              {account.data.name}
            </Link>
          ) : (
            "Loading account"
          )
        }
        actions={
          <div className="flex flex-col items-end gap-2">
            <div className="flex items-center gap-2">
              <Badge tone={statusTone(q.status)}>{label(q.status)}</Badge>
              <QuotationActions quotation={q} />
            </div>
          </div>
        }
      />

      {awaitingApproval ? (
        <div className="animate-fade-up mb-6 flex items-start gap-3 rounded-2xl border border-warning/25 bg-warning-soft px-5 py-4 text-[14px] text-warning">
          <Clock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p>
            Waiting for {label(q.approver_role).toLowerCase()} approval. The largest line discount is{" "}
            <span className="font-semibold">{q.items.reduce((max, i) => Math.max(max, Number(i.discount_pct)), 0)}%</span>.
          </p>
        </div>
      ) : null}

      <FactGrid>
        <Fact label="Subtotal">{money(q.subtotal)}</Fact>
        <Fact label="Discount">{money(q.discount_total)}</Fact>
        <Fact label="GST">{money(q.tax_total)}</Fact>
        <Fact label="Total" align="right">
          <span className="font-semibold text-ink">{money(q.total)}</span>
        </Fact>
      </FactGrid>

      <section className="mt-6" aria-labelledby="lines-h">
        <h2 id="lines-h" className="mb-3 text-[15px] font-semibold tracking-tight text-ink">
          Items
        </h2>
        <DataTable
          columns={LINE_COLUMNS}
          rows={q.items}
          rowKey={(i) => i.id}
          loading={false}
          error={null}
          emptyTitle="No items on this quotation"
        />
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card className="animate-fade-up">
          <CardHeader>
            <CardTitle>Terms</CardTitle>
          </CardHeader>
          <p className="px-6 pb-6 pt-4 text-[14px] leading-relaxed text-ink-muted">{q.terms ?? "No terms recorded."}</p>
        </Card>
        <Card className="animate-fade-up">
          <CardHeader>
            <CardTitle>Validity</CardTitle>
          </CardHeader>
          <dl className="grid grid-cols-2 gap-6 px-6 pb-6 pt-4">
            <div>
              <dt className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">Valid until</dt>
              <dd className="mt-1.5 text-[14px] text-ink">{date(q.valid_until)}</dd>
            </div>
            <div>
              <dt className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">Created</dt>
              <dd className="mt-1.5 text-[14px] text-ink">{date(q.created_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </>
  );
}

function BackLink() {
  return (
    <Link
      href="/quotations"
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      Quotations
    </Link>
  );
}
