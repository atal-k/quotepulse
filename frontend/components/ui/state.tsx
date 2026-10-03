import { AlertTriangle, Inbox } from "lucide-react";

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="animate-fade-up flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <div className="grid h-11 w-11 place-items-center rounded-full bg-surface-muted text-ink-faint">
        <Inbox className="h-5 w-5" aria-hidden />
      </div>
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint ? <p className="max-w-sm text-sm text-ink-muted">{hint}</p> : null}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="animate-fade-up flex items-start gap-3 px-6 py-5 text-sm text-danger">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p>{message}</p>
    </div>
  );
}
