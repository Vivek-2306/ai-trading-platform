import { BacktestCard } from "@/components/backtest-cards";
import { Card } from "@/components/ui/card";
import { getBacktests } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Backtests() {
  const runs = await getBacktests(40);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Backtests</h1>
        <p className="mt-1 text-muted">
          How the rules would have done on past candles, with fees and slippage, against simply
          buying and holding. The past does not predict the future, and a result from few trades is
          mostly noise. The most recent fifth of history is locked so it cannot be tuned on.
        </p>
      </div>
      {runs === null ? (
        <Card>
          <h2 className="font-medium">Backtests unavailable</h2>
          <p className="mt-2 text-sm text-muted">The API did not answer.</p>
        </Card>
      ) : runs.length === 0 ? (
        <Card>
          <h2 className="font-medium">No backtests yet</h2>
          <p className="mt-2 text-sm text-muted">
            Run one: <code>uv run python -m app.backtest run --symbol BTC/USDT --timeframe 1d</code>
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {runs.map((run) => (
            <BacktestCard key={run.id} run={run} />
          ))}
        </div>
      )}
    </div>
  );
}
