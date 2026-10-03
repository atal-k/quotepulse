"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Fact, FactGrid } from "@/components/data/facts";
import { PageHeader } from "@/components/data/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/state";
import { useProduct } from "@/lib/api/queries";
import { available } from "@/lib/inventory";
import { label, money } from "@/lib/format";

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const product = useProduct(id);

  if (product.isError) {
    return (
      <>
        <BackLink />
        <Card className="mt-6">
          <ErrorState message={product.error.message} />
        </Card>
      </>
    );
  }

  if (product.isPending || !product.data) {
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

  const p = product.data;
  const qty = available(p);
  const low = qty <= Number(p.reorder_level);
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={label(p.category)}
        title={p.name}
        description={<span className="font-mono">{p.sku}</span>}
        actions={<Badge tone={p.is_active ? "success" : "neutral"}>{p.is_active ? "Active" : "Inactive"}</Badge>}
      />

      <FactGrid>
        <Fact label="Unit price">{money(p.unit_price)}</Fact>
        <Fact label="GST">{`${p.tax_pct}%`}</Fact>
        <Fact label="Lead time">{`${p.lead_time_days} days`}</Fact>
        <Fact label="Min. order" align="right">
          {`${Number(p.min_order_qty).toLocaleString("en-IN")} ${p.unit}`}
        </Fact>
      </FactGrid>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card className="animate-fade-up">
          <CardHeader>
            <CardTitle>Stock</CardTitle>
            {low ? <Badge tone="warning">Low</Badge> : null}
          </CardHeader>
          <dl className="grid grid-cols-3 gap-6 px-6 pb-6 pt-5">
            <div>
              <dt className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">On hand</dt>
              <dd className="mt-1.5 text-[18px] font-semibold tabular-nums text-ink">
                {Number(p.stock_qty).toLocaleString("en-IN")}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">Reserved</dt>
              <dd className="mt-1.5 text-[18px] font-semibold tabular-nums text-ink">
                {Number(p.reserved_qty).toLocaleString("en-IN")}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">Available</dt>
              <dd className={`mt-1.5 text-[18px] font-semibold tabular-nums ${low ? "text-warning" : "text-ink"}`}>
                {qty.toLocaleString("en-IN")}
              </dd>
            </div>
          </dl>
          <p className="border-t border-line-soft px-6 py-4 text-[13px] text-ink-muted">
            Reorder level {Number(p.reorder_level).toLocaleString("en-IN")} {p.unit}.
          </p>
        </Card>

        <Card className="animate-fade-up">
          <CardHeader>
            <CardTitle>Pricing</CardTitle>
          </CardHeader>
          <p className="px-6 pb-6 pt-4 text-[14px] leading-relaxed text-ink-muted">
            Quotations take this unit price and GST rate from the catalog at the moment they are priced. Changing
            the catalog does not change a quotation that is already sent or accepted.
          </p>
          <p className="px-6 pb-6 text-[13px]">
            <Link href="/quotations" className="font-medium text-accent-strong hover:underline">
              View quotations
            </Link>
          </p>
        </Card>
      </div>
    </>
  );
}

function BackLink() {
  return (
    <Link
      href="/products"
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      Products
    </Link>
  );
}
