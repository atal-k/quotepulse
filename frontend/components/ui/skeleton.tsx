import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton rounded-md", className)} />;
}

export function TableSkeleton({ rows = 6, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="divide-y divide-line-soft" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, row) => (
        <div
          key={row}
          className="grid gap-4 px-6 py-4"
          style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
        >
          {Array.from({ length: columns }).map((_, column) => (
            <Skeleton key={column} className={cn("h-4", column === 0 ? "w-3/4" : "w-1/2")} />
          ))}
        </div>
      ))}
    </div>
  );
}
