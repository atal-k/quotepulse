"use client";

import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useApproveQuotation } from "@/hooks/use-sales-actions";
import { errorMessage } from "@/lib/api/client";
import { useMe } from "@/lib/api/queries";
import { canApprove } from "@/lib/api/actions";
import { label } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Approves a quotation that is waiting for review. Reusable on purpose: the quotation detail page
 * and the Phase 4 Approval Inbox both render this, so the call and its permission display live in
 * one place. The server enforces the tier; this only decides what to show.
 */
export function ApproveButton({
  quotationId,
  approverRole,
  className,
  onApproved,
}: {
  quotationId: string;
  approverRole: string | null | undefined;
  className?: string;
  onApproved?: () => void;
}) {
  const me = useMe();
  const approve = useApproveQuotation(quotationId);
  const allowed = canApprove(me.data?.role, approverRole);

  if (!allowed) {
    return (
      <p className={cn("text-[13px] text-warning", className)}>
        Needs {label(approverRole).toLowerCase()} approval
      </p>
    );
  }

  return (
    <div className={cn("flex flex-col items-end gap-1", className)}>
      <Button
        onClick={() => approve.mutate(undefined, { onSuccess: onApproved })}
        disabled={approve.isPending || me.isPending}
      >
        <Check className="h-4 w-4" aria-hidden />
        {approve.isPending ? "Approving" : "Approve"}
      </Button>
      {approve.isError ? (
        <p role="alert" className="text-[12px] text-danger">
          {errorMessage(approve.error, "Could not approve this quotation.")}
        </p>
      ) : null}
    </div>
  );
}
