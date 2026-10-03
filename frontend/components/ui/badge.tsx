import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-medium ring-1 ring-inset",
  {
    variants: {
      tone: {
        neutral: "bg-surface-muted text-ink-muted ring-line",
        accent: "bg-accent-soft text-accent-strong ring-accent/20",
        success: "bg-success-soft text-success ring-success/20",
        warning: "bg-warning-soft text-warning ring-warning/25",
        danger: "bg-danger-soft text-danger ring-danger/20",
        info: "bg-info-soft text-info ring-info/20",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

/** One place that decides how a domain status looks, so the same status is the same colour
 * everywhere it appears. */
export function statusTone(status: string | null | undefined): BadgeProps["tone"] {
  switch (status) {
    case "customer":
    case "won":
    case "accepted":
    case "delivered":
    case "paid":
    case "qualified":
      return "success";
    case "proposal":
    case "negotiation":
    case "contacted":
    case "sent":
    case "approved":
    case "shipped":
    case "processing":
    case "issued":
      return "info";
    case "pending_approval":
    case "partially_paid":
    case "prospect":
      return "warning";
    case "lost":
    case "rejected":
    case "disqualified":
    case "expired":
    case "inactive":
    case "void":
      return "danger";
    case "discovery":
    case "draft":
    case "new":
    case "confirmed":
      return "accent";
    default:
      return "neutral";
  }
}
