import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="animate-fade-up flex flex-wrap items-end justify-between gap-4 pb-8">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-accent">{eyebrow}</p>
        ) : null}
        <h1 className="mt-1.5 truncate text-[28px] font-semibold leading-tight tracking-tight text-ink">{title}</h1>
        {description ? <div className="mt-1.5 text-sm text-ink-muted">{description}</div> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}
