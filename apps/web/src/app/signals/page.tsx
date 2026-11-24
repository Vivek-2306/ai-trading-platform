import { AutoRefresh } from "@/components/auto-refresh";
import { ActionBadge, formatCandleTime, SignalCard } from "@/components/signal-card";
import { Card } from "@/components/ui/card";
import { getLatestSignals, getRecentSignals } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Signals() {
  const [latest, recent] = await Promise.all([getLatestSignals(), getRecentSignals(20)]);

  return (
    <div className="space-y-6">
      <AutoRefresh seconds={60} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Signals</h1>
        <p className="mt-1 text-muted">
          Research output from plain, tested rules. Not financial advice. NO TRADE is a valid
          answer, and agreement is a score of how much the rules agree, not a chance of winning.
        </p>
      </div>

      {latest === null ? (
        <Card>
          <h2 className="font-medium">Signals unavailable</h2>
          <p className="mt-2 text-sm text-muted">
            The API did not answer. Check the system status page.
          </p>
        </Card>
      ) : latest.length === 0 ? (
        <Card>
          <h2 className="font-medium">No signals yet</h2>
          <p className="mt-2 text-sm text-muted">
            The signal job runs ten minutes past every hour, once candles are loaded.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {latest.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      )}

      {recent && recent.length > 0 && (
        <section aria-labelledby="history">
          <h2 id="history" className="mb-3 text-lg font-semibold">
            Recent history
          </h2>
          <Card className="p-2 sm:p-4">
            <ul className="divide-y divide-foreground/10">
              {recent.map((signal) => (
                <li
                  key={signal.id}
                  className="flex flex-wrap items-center justify-between gap-2 px-2 py-3"
                >
                  <div>
                    <span className="font-medium">{signal.symbol}</span>{" "}
                    <span className="text-sm text-muted">
                      {signal.timeframe} · {formatCandleTime(signal.candle_ts)}
                    </span>
                  </div>
                  <ActionBadge action={signal.action} />
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}
    </div>
  );
}
