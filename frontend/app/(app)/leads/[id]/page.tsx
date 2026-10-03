"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Timeline } from "@/components/data/timeline";
import { Fact, FactGrid } from "@/components/data/facts";
import { PageHeader } from "@/components/data/page-header";
import { Badge, statusTone } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/state";
import { useLead } from "@/lib/api/queries";
import { label } from "@/lib/format";

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const lead = useLead(id);

  if (lead.isError) {
    return (
      <>
        <BackLink />
        <Card className="mt-6">
          <ErrorState message={lead.error.message} />
        </Card>
      </>
    );
  }

  if (lead.isPending || !lead.data) {
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

  const l = lead.data;
  const bant = l.qualification;
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow="Lead"
        title={l.name}
        description={l.company_name ?? undefined}
        actions={<Badge tone={statusTone(l.status)}>{label(l.status)}</Badge>}
      />

      <FactGrid>
        <Fact label="Email">{l.email ?? "—"}</Fact>
        <Fact label="Phone" mono>
          {l.phone ?? "—"}
        </Fact>
        <Fact label="Source">{label(l.source)}</Fact>
        <Fact label="Score" align="right">
          {l.score === null ? "—" : `${l.score} / 100`}
        </Fact>
      </FactGrid>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card className="animate-fade-up">
          <CardHeader>
            <CardTitle>Qualification</CardTitle>
          </CardHeader>
          <dl className="grid gap-x-8 gap-y-5 px-6 pb-6 pt-5 sm:grid-cols-2">
            {bant ? (
              (["budget", "authority", "need", "timeline"] as const).map((key) => (
                <div key={key}>
                  <dt className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">{label(key)}</dt>
                  <dd className="mt-1.5 text-[14px] leading-relaxed text-ink">{bant[key] ?? "—"}</dd>
                </div>
              ))
            ) : (
              <p className="text-sm text-ink-muted sm:col-span-2">Not qualified yet. BANT notes appear here once captured.</p>
            )}
          </dl>
          {l.converted_account_id ? (
            <div className="border-t border-line-soft px-6 py-4 text-[13px] text-ink-muted">
              Converted to{" "}
              <Link className="font-medium text-accent-strong hover:underline" href={`/accounts/${l.converted_account_id}`}>
                its account
              </Link>
            </div>
          ) : null}
        </Card>

        <div className="lg:sticky lg:top-8 lg:self-start">
          <Timeline entityType="lead" entityId={l.id} />
        </div>
      </div>
    </>
  );
}

function BackLink() {
  return (
    <Link
      href="/leads"
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
      Leads
    </Link>
  );
}
