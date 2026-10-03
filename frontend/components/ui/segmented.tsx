"use client";

import { cn } from "@/lib/utils";

export interface SegmentOption<V extends string> {
  value: V | "";
  label: string;
}

/** Status filter chips. An empty value means "all". */
export function SegmentedControl<V extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: SegmentOption<V>[];
  value: V | "";
  onChange: (next: V | "") => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1 rounded-xl bg-surface-muted p-1">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value || "all"}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-[13px] font-medium transition-[background-color,color,box-shadow] duration-150",
              active
                ? "bg-surface text-ink shadow-sm ring-1 ring-line"
                : "text-ink-muted hover:text-ink",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
