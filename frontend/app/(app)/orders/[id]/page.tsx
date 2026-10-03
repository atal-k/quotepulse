"use client";

import { ArrowLeft, Truck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DataTable, type Column } from "@/components/data/data-table";
import { Fact, FactGrid } from "@/components/data/facts";
import { PageHeader } from "@/components/data/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/state";
import { errorMessage } from "@/lib/api/client";
import { type OrderItem, useAccount, useOrder } from "@/lib/api/queries";
import { useDeliverOrder, useProcessOrder, useShipOrder } from "@/hooks/use-sales-actions";
import { date, label, money } from "@/lib/format";

const LINE_COLUMNS: Column<OrderItem>[] = [
  { key: "description", header: "Item", cell: (i) => i.description },
  { key: "qty", header: "Qty", align: "right", cell: (i) => Number(i.qty).toLocaleString("en-IN") },
  { key: "price", header: "Unit price", align: "right", cell: (i) => money(i.unit_price) },
  { key: "tax", header: "GST", align: "right", cell: (i) => `${i.tax_pct}%` },
  { key: "total", header: "Line total", align: "right", cell: (i) => <span className="font-medium">{money(i.line_total)}</span> },
];

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const order = useOrder(id);
  const account = useAccount(order.data?.account_id ?? "");
  const process = useProcessOrder(id);
  const ship = useShipOrder(id);
  const deliver = useDeliverOrder(id);

  if (order.isError) {
    return (
      <>
        <BackLink />
        <Card className="mt-6">
          <ErrorState message={order.error.message} />
        </Card>
      </>
    );
  }

  if (order.isPending || !order.data) {
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

  const o = order.data;
  const canProcess = o.status === "confirmed";
  const canShip = o.status === "processing";
  const canDeliver = o.status === "shipped";
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow="Order"
        title={<span className="font-mono">{o.number}</span>}
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
              <Badge tone={statusTone(o.status)}>{label(o.status)}</Badge>
              <Button variant="secondary" onClick={() => process.mutate()} disabled={!canProcess || process.isPending}>
                {process.isPending ? "Starting" : "Start processing"}
              </Button>
              <Button onClick={() => ship.mutate()} disabled={!canShip || ship.isPending}>
                <Truck className="h-4 w-4" aria-hidden />
                {ship.isPending ? "Shipping" : "Ship order"}
              </Button>
              <Button variant="secondary" onClick={() => deliver.mutate()} disabled={!canDeliver || deliver.isPending}>
                {deliver.isPending ? "Marking" : "Mark delivered"}
              </Button>
            </div>
            {canProcess ? (
              <p className="text-[12px] text-ink-muted">Start processing first, then ship.</p>
            ) : null}
            {process.isError ? (
              <p role="alert" className="text-[12px] text-danger">
                {errorMessage(process.error, "Could not start processing this order.")}
              </p>
            ) : null}
            {deliver.isError ? (
              <p role="alert" className="text-[12px] text-danger">
                {errorMessage(deliver.error, "Could not mark this order delivered.")}
              </p>
            ) : null}
            {ship.isError ? (
              <p role="alert" className="text-[12px] text-danger">
                {errorMessage(ship.error, "Could not ship this order.")}
              </p>
            ) : null}
          </div>
        }
      />

      <FactGrid>
        <Fact label="Subtotal">{money(o.subtotal)}</Fact>
        <Fact label="Discount">{money(o.discount_total)}</Fact>
        <Fact label="GST">{money(o.tax_total)}</Fact>
        <Fact label="Total" align="right">
          <span className="font-semibold text-ink">{money(o.total)}</span>
        </Fact>
      </FactGrid>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section aria-labelledby="order-lines">
          <h2 id="order-lines" className="mb-3 text-[15px] font-semibold tracking-tight text-ink">
            Items
          </h2>
          <DataTable
            columns={LINE_COLUMNS}
            rows={o.items}
            rowKey={(i) => i.id}
            loading={false}
            error={null}
            emptyTitle="No items on this order"
          />
        </section>

        <div className="space-y-6">
          <Card className="animate-fade-up">
            <CardHeader>
              <CardTitle>Delivery</CardTitle>
            </CardHeader>
            <dl className="space-y-5 px-6 pb-6 pt-4">
              <div>
                <dt className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">Expected</dt>
                <dd className="mt-1.5 text-[14px] text-ink">{date(o.expected_delivery_date)}</dd>
              </div>
              <div>
                <dt className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">Ship to</dt>
                <dd className="mt-1.5 text-[14px] leading-relaxed text-ink">{o.shipping_address ?? "—"}</dd>
              </div>
            </dl>
          </Card>
          <Card className="animate-fade-up">
            <CardHeader>
              <CardTitle>Source</CardTitle>
            </CardHeader>
            <p className="px-6 pb-6 pt-4 text-[14px] text-ink-muted">
              Accepted quotation{" "}
              <Link className="font-medium text-accent-strong hover:underline" href={`/quotations/${o.quotation_id}`}>
                view
              </Link>
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}

function BackLink() {
  return (
    <Link
      href="/orders"
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      Orders
    </Link>
  );
}
