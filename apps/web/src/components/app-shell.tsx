import { Activity, CandlestickChart, Compass, FlaskConical, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/charts", label: "Charts", icon: CandlestickChart },
  { href: "/signals", label: "Signals", icon: Compass },
  { href: "/backtests", label: "Backtests", icon: FlaskConical },
  { href: "/status", label: "Status", icon: Activity },
];

/** Top bar on every size; the nav moves to a bottom bar on phones. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-5xl flex-col px-4 pb-[calc(6rem+env(safe-area-inset-bottom))] sm:pb-8">
      <header className="glass sticky top-3 z-10 mt-3 flex items-center justify-between rounded-2xl px-4 py-2">
        <Link href="/" className="font-semibold tracking-tight">
          AI Trading <span className="text-accent">Platform</span>
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 sm:flex">
          {NAV.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="rounded-lg px-3 py-2 text-sm text-muted hover:text-foreground"
            >
              {label}
            </Link>
          ))}
        </nav>
        <ThemeToggle />
      </header>
      <main className="flex-1 py-6">{children}</main>
      <nav
        aria-label="Main"
        className="glass fixed inset-x-3 bottom-3 z-10 flex justify-around rounded-2xl p-1 sm:hidden"
      >
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex min-h-12 flex-1 flex-col items-center justify-center gap-0.5 rounded-xl text-xs text-muted"
          >
            <Icon size={18} />
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
