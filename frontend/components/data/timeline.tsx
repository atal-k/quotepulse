"use client";

import { Mail, MessageCircle, Notebook, Phone, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { type Activity, type Page, useTimeline } from "@/lib/api/queries";
import { dateTime, label } from "@/lib/format";

const ICONS: Record<Activity["type"], typeof Phone> = {
  call: Phone,
  email: Mail,
  meeting: Users,
  note: Notebook,
  chat: MessageCircle,
  whatsapp: MessageCircle,
};

/** Activity thread for any parent record. Newest first, as the API returns it. */
export function Timeline({
  entityType,
  entityId,
}: {
  entityType: Activity["entity_type"];
  entityId: string;
}) {
  const query = useTimeline(entityType, entityId);
  const page = query.data as Page<Activity> | undefined;

  return (
    <Card className="animate-fade-up">
      <CardHeader>
        <CardTitle>Activity</CardTitle>
        {page ? <span className="text-[13px] text-ink-muted tabular-nums">{page.total} logged</span> : null}
      </CardHeader>
      <div className="px-6 pb-6 pt-4">
        {query.isPending ? (
          <TableSkeleton rows={3} columns={2} />
        ) : query.isError ? (
          <ErrorState message={query.error.message} />
        ) : !page || page.items.length === 0 ? (
          <EmptyState title="No activity yet" hint="Calls, emails and notes logged against this record appear here." />
        ) : (
          <ol className="relative space-y-5 border-l border-line pl-6">
            {page.items.map((activity) => {
              const Icon = ICONS[activity.type];
              return (
                <li key={activity.id} className="animate-fade-up relative">
                  <span className="absolute -left-[33px] grid h-6 w-6 place-items-center rounded-full bg-surface ring-1 ring-line">
                    <Icon className="h-3 w-3 text-accent" aria-hidden />
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">{label(activity.type)}</Badge>
                    <time className="text-[12px] text-ink-faint tabular-nums" dateTime={activity.occurred_at}>
                      {dateTime(activity.occurred_at)}
                    </time>
                  </div>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-ink">{activity.body ?? activity.subject}</p>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </Card>
  );
}
