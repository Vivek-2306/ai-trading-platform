import Link from "next/link";
import { Card } from "@/components/ui/card";
import type { BacktestSummary } from "@/lib/api";
import { day, num, pct, SEGMENT_LABEL } from "@/lib/format";
import { cn } from "@/lib/utils";

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd
        className={cn(
          "text-base font-semibold tabular-nums",
          tone === "good" && "text-good",
          tone === "bad" && "text-bad",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

const tone = (v: number | undefined) => (v === undefined ? undefined : v >= 0 ? "good" : "bad");

/** One stored run: the headline numbers, the benchmark verdict, and any warnings. */
export function BacktestCard({ run }: { run: BacktestSummary }) {
  const m = run.metrics;
  const walk = run.segment === "walk_forward";
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">
            {run.symbol} <span className="text-muted">{run.timeframe}</span>
          </h3>
          <p className="text-sm text-muted">
            {SEGMENT_LABEL[run.segment] ?? run.segment} · {day(run.range_start)} to{" "}
            {day(run.range_end)}
          </p>
        </div>
        <Link
          href={`/backtests/${run.id}`}
          className="rounded-full bg-accent/15 px-3 py-1.5 text-sm font-medium text-accent"
        >
          Details
        </Link>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-3">
        {walk ? (
          <>
            <Stat label="Windows" value={`${m.profitable_windows ?? 0}/${m.windows ?? 0} up`} />
            <Stat
              label="Mean window"
              value={pct(m.mean_window_return_pct)}
              tone={tone(m.mean_window_return_pct ?? undefined)}
            />
            <Stat label="Trades" value={String(m.total_trades ?? 0)} />
          </>
        ) : (
          <>
            <Stat label="Return" value={pct(m.total_return_pct)} tone={tone(m.total_return_pct)} />
            <Stat label="Max drawdown" value={pct(m.max_drawdown_pct)} />
            <Stat label="Trades" value={String(m.trades ?? 0)} />
            <Stat label="Win rate" value={pct(m.win_rate_pct, 0)} />
            <Stat label="Profit factor" value={num(m.profit_factor)} />
            <Stat label="Buy and hold" value={pct(run.benchmark.benchmark_return_pct)} />
          </>
        )}
      </dl>
      {run.benchmark.verdict && <p className="mt-3 text-sm">{run.benchmark.verdict}</p>}
      {(m.warnings ?? []).map((w) => (
        <p key={w} role="note" className="mt-2 text-sm text-bad">
          {w}
        </p>
      ))}
    </Card>
  );
}
