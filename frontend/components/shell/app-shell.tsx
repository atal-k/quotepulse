"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText, Building2, LogOut, Target, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
import { clearToken, getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/accounts", label: "Accounts", icon: Building2 },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/opportunities", label: "Opportunities", icon: Target },
  { href: "/quotations", label: "Quotations", icon: FileText },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const hasToken = typeof window !== "undefined" && Boolean(getToken());

  useEffect(() => {
    if (!hasToken) router.replace("/login");
  }, [hasToken, router]);

  const me = useQuery({
    queryKey: ["me"],
    enabled: hasToken,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/me");
      if (error || !data) throw new Error("Session expired");
      return data;
    },
  });

  function signOut() {
    clearToken();
    router.replace("/login");
  }

  return (
    <div className="flex min-h-dvh bg-background">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col bg-sidebar px-4 py-6 text-sidebar-ink md:flex">
        <Link href="/accounts" className="flex items-center gap-2.5 px-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/10 text-sm font-semibold text-sidebar-ink-strong">
            Q
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-sidebar-ink-strong">QuotePulse</span>
        </Link>

        <nav aria-label="Primary" className="mt-10 flex flex-col gap-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] transition-colors duration-150",
                  active
                    ? "bg-sidebar-active text-sidebar-ink-strong"
                    : "text-sidebar-ink hover:bg-white/5 hover:text-sidebar-ink-strong",
                )}
              >
                <Icon className={cn("h-4 w-4 transition-colors", active ? "text-[#7fd6c9]" : "opacity-70")} aria-hidden />
                {label}
                {active ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#7fd6c9]" aria-hidden /> : null}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto rounded-xl bg-white/5 p-3">
          {me.isPending ? (
            <div className="space-y-2">
              <Skeleton className="h-3.5 w-28 bg-white/10" />
              <Skeleton className="h-3 w-16 bg-white/10" />
            </div>
          ) : me.data ? (
            <>
              <p className="truncate text-[13px] font-medium text-sidebar-ink-strong">{me.data.full_name}</p>
              <p className="text-[12px] capitalize text-sidebar-ink/80">{me.data.role}</p>
            </>
          ) : null}
          <button
            type="button"
            onClick={signOut}
            className="mt-3 flex items-center gap-2 text-[12px] font-medium text-sidebar-ink transition-colors hover:text-sidebar-ink-strong"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden />
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <nav aria-label="Primary mobile" className="flex gap-1 overflow-x-auto border-b border-line bg-surface px-4 py-2 md:hidden">
          {NAV.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "shrink-0 rounded-lg px-3 py-1.5 text-[13px] font-medium",
                pathname.startsWith(href) ? "bg-accent-soft text-accent-strong" : "text-ink-muted",
              )}
            >
              {label}
            </Link>
          ))}
        </nav>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8 sm:px-10 lg:py-10">{children}</main>
      </div>
    </div>
  );
}
