import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function FactGrid({ children }: { children: ReactNode }) {
  return (
    <Card className="animate-fade-up grid grid-cols-2 gap-x-8 gap-y-6 p-6 sm:grid-cols-4">{children}</Card>
  );
}

export function Fact({
  label,
  children,
  mono = false,
  align = "left",
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
  align?: "left" | "right";
}) {
  return (
    <div className={cn("min-w-0", align === "right" && "sm:text-right")}>
      <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-faint">{label}</p>
      <p className={cn("mt-1.5 truncate text-[15px] text-ink tabular-nums", mono && "font-mono text-[14px]")}>
        {children}
      </p>
    </div>
  );
}
