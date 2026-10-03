"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api/client";
import { setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const { data, error: failure } = await api.POST("/api/v1/auth/login", {
      body: { email, password },
    });
    setPending(false);
    if (failure || !data) {
      setError(errorMessage(failure, "Could not sign you in. Check your email and password."));
      return;
    }
    setToken(data.access_token);
    router.replace("/accounts");
  }

  return (
    <main className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-sidebar p-12 text-sidebar-ink lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 h-[28rem] w-[28rem] rounded-full bg-accent/30 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-40 left-10 h-[24rem] w-[24rem] rounded-full bg-[#2dd4bf]/10 blur-3xl"
        />
        <div className="relative flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/10 text-sm font-semibold text-sidebar-ink-strong">
            Q
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-sidebar-ink-strong">QuotePulse</span>
        </div>
        <div className="relative max-w-md">
          <p className="text-[13px] font-medium uppercase tracking-[0.16em] text-[#7fd6c9]">
            Quote to cash, without the spreadsheet
          </p>
          <h1 className="mt-4 text-[40px] font-semibold leading-[1.1] tracking-tight text-sidebar-ink-strong">
            Every lead, quote and invoice in one calm place.
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed text-sidebar-ink">
            Built for industrial sales teams in India: GST-ready accounts, stock-aware quotes and discount
            approvals that happen in the app, not in WhatsApp.
          </p>
        </div>
        <p className="relative text-[12px] text-sidebar-ink/70">Demo workspace · synthetic data</p>
      </aside>

      <section className="flex items-center justify-center bg-background px-6 py-12 sm:px-12">
        <div className="animate-fade-up w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <span className="text-[15px] font-semibold tracking-tight text-ink">QuotePulse</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-ink">Sign in</h2>
          <p className="mt-1.5 text-sm text-ink-muted">Use your team email to continue.</p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4" noValidate>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink">Email</span>
              <Input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="rep@quotepulse.dev"
                disabled={pending}
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink">Password</span>
              <Input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={pending}
              />
            </label>

            {error ? (
              <p role="alert" className="animate-fade-up rounded-lg bg-danger-soft px-3 py-2.5 text-[13px] text-danger">
                {error}
              </p>
            ) : null}

            <Button type="submit" className="mt-2 w-full" disabled={pending || !email || !password}>
              {pending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Signing in
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </>
              )}
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
}
