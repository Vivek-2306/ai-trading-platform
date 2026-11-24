import Link from "next/link";
import { notFound } from "next/navigation";
import { EquityChart } from "@/components/equity-chart";
import { Card } from "@/components/ui/card";
import { type BacktestDetail, getBacktest } from "@/lib/api";
import { day, money, num, pct, SEGMENT_LABEL } from "@/lib/format";

export const dynamic = "force-dynamic";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-base font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function Windows({ run }: { run: BacktestDetail }) {
  const windows = run.details.windows ?? [];
  if (windows.length === 0) return null;
  return (
    <Card className="overflow-x-auto p-3 sm:p-5">
      <h2 className="font-medium">Walk-forward windows</h2>
      <p className="mt-1 text-sm text-muted">
        The strategy has no fitted settings, so this shows whether it behaves consistently across
        different stretches of history.
      </p>
      <table className="mt-3 w-full min-w-96 text-sm">
        <thead className="text-left text-muted">
          <tr>
            <th className="py-1 pr-3 font-normal">From</th>
            <th className="py-1 pr-3 font-normal">To</th>
            <th className="py-1 pr-3 text-right font-normal">Trades</th>
            <th className="py-1 pr-3 text-right font-normal">Return</th>
            <th className="py-1 text-right font-normal">Drawdown</th>
          </tr>
        </thead>
        <tbody>
          {windows.map((w) => (
            <tr key={w.start} className="border-t border-foreground/10">
              <td className="py-1.5 pr-3">{day(w.start)}</td>
              <td className="py-1.5 pr-3">{day(w.end)}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{w.trades}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{pct(w.return_pct)}</td>
              <td className="py-1.5 text-right tabular-nums">{pct(w.max_drawdown_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export default async function BacktestPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const runId = Number(id);
  if (!Number.isInteger(runId) || runId < 1) notFound();
  const run = await getBacktest(runId);
  if (run === undefined) notFound();
  if (run === null) {
    return (
      <Card>
        <h1 className="font-medium">Backtest unavailable</h1>
        <p className="mt-2 text-sm text-muted">The API did not answer.</p>
      </Card>
    );
  }

  const m = run.metrics;
  const walk = run.segment === "walk_forward";
  return (
    <div className="space-y-6">
      <div>
        <Link href="/backtests" className="text-sm text-accent">
          ← All backtests
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          {run.symbol} {run.timeframe}
        </h1>
        <p className="text-muted">
          {SEGMENT_LABEL[run.segment] ?? run.segment} · {day(run.range_start)} to{" "}
          {day(run.range_end)} · {run.candle_count.toLocaleString("en-US")} candles
        </p>
      </div>

      <Card>
        <p className="text-sm">
          A simulation of the past with fees ({String(run.config.fee_pct ?? "?")}% per fill) and
          slippage ({String(run.config.slippage_bps ?? "?")} bps). It is not a forecast and not
          advice.
          {run.segment === "oos"
            ? " This locked period was judged once; it can no longer be used to tune."
            : " In-sample: the rules were designed with this history in view, so treat it as optimistic. Only the locked out-of-sample judgement is a fair test."}
        </p>
        {run.benchmark.verdict && <p className="mt-2 font-medium">{run.benchmark.verdict}</p>}
        {(m.warnings ?? []).map((w) => (
          <p key={w} role="note" className="mt-2 text-sm text-bad">
            {w}
          </p>
        ))}
      </Card>

      {!walk && (
        <Card>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Metric label="Return" value={pct(m.total_return_pct)} />
            <Metric label="Buy and hold" value={pct(run.benchmark.benchmark_return_pct)} />
            <Metric label="Max drawdown" value={pct(m.max_drawdown_pct)} />
            <Metric label="Sharpe" value={num(m.sharpe)} />
            <Metric label="Trades" value={String(m.trades ?? 0)} />
            <Metric label="Win rate" value={pct(m.win_rate_pct, 0)} />
            <Metric label="Profit factor" value={num(m.profit_factor)} />
            <Metric label="Expectancy / trade" value={money(m.expectancy)} />
            <Metric label="Net P&L" value={money(m.net_pnl)} />
            <Metric label="Before costs" value={money(m.gross_pnl)} />
            <Metric label="Fees paid" value={money(m.fees_paid)} />
            <Metric label="Time in market" value={pct(m.exposure_pct, 0)} />
          </dl>
        </Card>
      )}

      {!walk && (run.equity.times?.length ?? 0) > 0 && (
        <Card className="p-2 sm:p-5">
          <EquityChart curves={run.equity} />
        </Card>
      )}

      <Windows run={run} />

      {run.trades.length > 0 && (
        <Card className="overflow-x-auto p-3 sm:p-5">
          <h2 className="font-medium">Latest trades</h2>
          {run.trade_count !== undefined && run.trade_count > run.trades.length && (
            <p className="mt-1 text-sm text-muted">
              Showing the latest {run.trades.length} of {run.trade_count}.
            </p>
          )}
          <table className="mt-3 w-full min-w-[34rem] text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="py-1 pr-3 font-normal">Entered</th>
                <th className="py-1 pr-3 font-normal">Exit</th>
                <th className="py-1 pr-3 text-right font-normal">P&amp;L</th>
                <th className="py-1 text-right font-normal">R</th>
              </tr>
            </thead>
            <tbody>
              {run.trades
                .slice(-30)
                .reverse()
                .map((t) => (
                  <tr key={t.entry_ts} className="border-t border-foreground/10">
                    <td className="py-1.5 pr-3">{t.entry_ts.slice(0, 16).replace("T", " ")}</td>
                    <td className="py-1.5 pr-3">{t.exit_reason.replace("_", " ")}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{money(t.pnl)}</td>
                    <td className="py-1.5 text-right tabular-nums">{t.r_multiple}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Card>
      )}

      <p className="text-xs text-muted">
        Run {run.id} · config {run.config_hash} · code {run.code_version} · data{" "}
        {run.data_fingerprint.slice(0, 12)}
      </p>
    </div>
  );
}
