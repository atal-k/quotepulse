"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PAGE_SIZE, type Page } from "@/lib/api/queries";

export function Pagination({
  page,
  offset,
  onOffset,
}: {
  page: Page<unknown> | undefined;
  offset: number;
  onOffset: (next: number) => void;
}) {
  if (!page || page.total === 0) return null;
  const from = offset + 1;
  const to = Math.min(offset + PAGE_SIZE, page.total);
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < page.total;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between border-t border-line-soft px-6 py-3.5">
      <p className="text-[13px] text-ink-muted tabular-nums">
        {from}–{to} of {page.total}
      </p>
      <div className="flex items-center gap-1.5">
        <Button variant="secondary" size="sm" disabled={!hasPrev} onClick={() => onOffset(offset - PAGE_SIZE)}>
          <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={!hasNext} onClick={() => onOffset(offset + PAGE_SIZE)}>
          Next
          <ChevronRight className="h-3.5 w-3.5" aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
