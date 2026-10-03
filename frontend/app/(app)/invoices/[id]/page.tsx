"use client";

import { ArrowLeft, IndianRupee } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Fact, FactGrid } from "@/components/data/facts";
import { PageHeader } from "@/components/data/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/state";
import { errorMessage } from "@/lib/api/client";
import { useAccount, useInvoice } from "@/lib/api/queries";
import { useRecordPayment } from "@/hooks/use-sales-actions";
import { date, label, money } from "@/lib/format";

const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/;

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const invoice = useInvoice(id);
  const account = useAccount(invoice.data?.account_id ?? "");
  const pay = useRecordPayment(id);
  const [amount, setAmount] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  if (invoice.isError) {
    return (
      <>
        <BackLink />
        <Card className="mt-6">
          <ErrorState message={invoice.error.message} />
        </Card>
      </>
    );
  }

  if (invoice.isPending || !invoice.data) {
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

  const inv = invoice.data;
  const outstanding = (Number(inv.total) - Number(inv.amount_paid)).toFixed(2);
  const open = inv.status === "issued" || inv.status === "partially_paid";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    const value = amount.trim();
    if (!AMOUNT_PATTERN.test(value) || Number(value) <= 0) {
      setLocalError("Enter an amount in rupees, for example 1500 or 1500.50.");
      return;
    }
    if (Number(value) > Number(outstanding)) {
      setLocalError(`That is more than the ${money(outstanding)} still outstanding.`);
      return;
    }
    pay.mutate(value, { onSuccess: () => setAmount("") });
  }

  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow="Invoice"
        title={<span className="font-mono">{inv.number}</span>}
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
          <div className="flex items-center gap-2">
            <Badge tone={statusTone(inv.status)}>{label(inv.status)}</Badge>
            {inv.overdue ? <Badge tone="danger">Overdue</Badge> : null}
          </div>
        }
      />

      <FactGrid>
        <Fact label="Issued">{date(inv.issue_date)}</Fact>
        <Fact label="Due">{date(inv.due_date)}</Fact>
        <Fact label="Paid">{money(inv.amount_paid)}</Fact>
        <Fact label="Total" align="right">
          <span className="font-semibold text-ink">{money(inv.total)}</span>
        </Fact>
      </FactGrid>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="animate-fade-up">
          <CardHeader>
            <CardTitle>Order</CardTitle>
          </CardHeader>
          <p className="px-6 pb-6 pt-4 text-[14px] text-ink-muted">
            Billed for{" "}
            <Link className="font-medium text-accent-strong hover:underline" href={`/orders/${inv.order_id}`}>
              the shipped order
            </Link>
            . Outstanding balance: <span className="font-medium text-ink">{money(outstanding)}</span>.
          </p>
        </Card>

        <Card className="animate-fade-up">
          <CardHeader>
            <CardTitle>Record payment</CardTitle>
          </CardHeader>
          <div className="px-6 pb-6 pt-4">
            {open ? (
              <form onSubmit={submit} className="space-y-3" noValidate>
                <label className="block">
                  <span className="mb-1.5 block text-[13px] font-medium text-ink">Amount received (₹)</span>
                  <Input
                    inputMode="decimal"
                    placeholder={outstanding}
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                    disabled={pay.isPending}
                  />
                </label>
                <Button type="submit" className="w-full" disabled={pay.isPending || !amount}>
                  <IndianRupee className="h-4 w-4" aria-hidden />
                  {pay.isPending ? "Recording" : "Record payment"}
                </Button>
                {localError || pay.isError ? (
                  <p role="alert" className="text-[13px] text-danger">
                    {localError ?? errorMessage(pay.error, "Could not record this payment.")}
                  </p>
                ) : null}
                {pay.isSuccess && !localError ? (
                  <p className="text-[13px] text-success">Payment recorded.</p>
                ) : null}
              </form>
            ) : (
              <p className="text-[14px] text-ink-muted">
                {inv.status === "paid" ? "Fully paid. No further payments are needed." : "Payments are closed for this invoice."}
              </p>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}

function BackLink() {
  return (
    <Link
      href="/invoices"
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      Invoices
    </Link>
  );
}
