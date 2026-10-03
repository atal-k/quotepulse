"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  /** Render in the monospace face (identifiers, GST numbers, document numbers). */
  mono?: boolean;
  /** Mark the column that carries the row link, so the whole row is clickable. */
  primary?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string;
  /** Omit for lists without a detail page; no row is then a link. */
  rowHref?: (row: T) => string;
  loading: boolean;
  error: Error | null;
  emptyTitle: string;
  emptyHint?: string;
  footer?: ReactNode;
}

/**
 * The one list table used by every module. Whole rows link to the detail page, via a stretched
 * link on the primary cell, so there is no nested interactive markup.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  rowHref,
  loading,
  error,
  emptyTitle,
  emptyHint,
  footer,
}: DataTableProps<T>) {
  return (
    <Card className="animate-fade-up overflow-hidden">
      {error ? (
        <ErrorState message={error.message} />
      ) : loading || rows === undefined ? (
        <TableSkeleton rows={6} columns={columns.length} />
      ) : rows.length === 0 ? (
        <EmptyState title={emptyTitle} hint={emptyHint} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line-soft">
                {columns.map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    className={cn(
                      "px-6 py-3 text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint",
                      column.align === "right" && "text-right",
                    )}
                  >
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr
                  key={rowKey(row)}
                  className="animate-fade-up border-b border-line-soft transition-colors duration-150 last:border-0 hover:bg-surface-muted/70"
                  style={{ animationDelay: `${Math.min(index, 12) * 22}ms` }}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        "px-6 py-4 align-middle text-ink",
                        column.align === "right" && "text-right tabular-nums",
                        column.mono && "font-mono text-[13px] text-ink-muted",
                        column.primary && rowHref && "relative",
                      )}
                    >
                      {column.primary && rowHref ? (
                        <Link
                          href={rowHref(row)}
                          className="font-medium text-ink after:absolute after:inset-0 after:content-[''] focus-visible:outline-none hover:text-accent-strong"
                        >
                          {column.cell(row)}
                        </Link>
                      ) : (
                        column.cell(row)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {footer}
    </Card>
  );
}
