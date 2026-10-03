"use client";

import { CheckCheck, Send, Upload } from "lucide-react";

import { ApproveButton } from "@/components/approval/approve-button";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api/client";
import type { QuotationAction } from "@/lib/api/actions";
import { type Quotation } from "@/lib/api/queries";
import { useQuotationAction } from "@/hooks/use-sales-actions";
import { label } from "@/lib/format";

/**
 * The transition buttons for a quotation, chosen by its status. Each button calls the existing
 * endpoint; none of them builds or edits a quotation.
 */
export function QuotationActions({ quotation }: { quotation: Quotation }) {
  switch (quotation.status) {
    case "draft":
      return <ActionButton id={quotation.id} action="submit" label={quotation.approver_role ? "Submit for approval" : "Submit"} icon={Upload} />;
    case "pending_approval":
      return <ApproveButton quotationId={quotation.id} approverRole={quotation.approver_role} />;
    case "approved":
      return <ActionButton id={quotation.id} action="send" label="Mark sent" icon={Send} />;
    case "sent":
      return <ActionButton id={quotation.id} action="accept" label="Customer accepted" icon={CheckCheck} />;
    default:
      return null;
  }
}

function ActionButton({
  id,
  action,
  label: text,
  icon: Icon,
}: {
  id: string;
  action: QuotationAction;
  label: string;
  icon: typeof Send;
}) {
  const run = useQuotationAction(id, action);
  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant={action === "accept" ? "primary" : "secondary"} onClick={() => run.mutate()} disabled={run.isPending}>
        <Icon className="h-4 w-4" aria-hidden />
        {run.isPending ? `${label(action)}…` : text}
      </Button>
      {run.isError ? (
        <p role="alert" className="text-[12px] text-danger">
          {errorMessage(run.error, `Could not ${action} this quotation.`)}
        </p>
      ) : null}
    </div>
  );
}
