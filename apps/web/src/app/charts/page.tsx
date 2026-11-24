import { ChartControls, type ChartTimeframe, TIMEFRAMES } from "@/components/chart-controls";
import { LiveChart } from "@/components/live-chart";
import { Card } from "@/components/ui/card";
import { getCandles, getInstruments } from "@/lib/api";
import { toChartData } from "@/lib/chart-data";
import { formingCandle } from "@/lib/live";

export const dynamic = "force-dynamic";

const SECONDS = { "1h": 3600, "1d": 86400 } as const;

function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <h2 className="font-medium">{title}</h2>
      <p className="mt-2 text-sm text-muted">{children}</p>
    </Card>
  );
}

export default async function Charts({
  searchParams,
}: {
  searchParams: Promise<{ instrument?: string; timeframe?: string }>;
}) {
  const query = await searchParams;
  const instruments = await getInstruments();
  const heading = <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Charts</h1>;

  if (instruments === null) {
    return (
      <div className="space-y-6">
        {heading}
        <Notice title="Market data unavailable">
          The API did not answer. Check the system status page.
        </Notice>
      </div>
    );
  }
  const selected = instruments.find((i) => String(i.id) === query.instrument) ?? instruments[0];
  if (!selected) {
    return (
      <div className="space-y-6">
        {heading}
        <Notice title="No market data yet">
          Load history first: run the <code>backfill_candles</code> task, or wait for the hourly
          update job.
        </Notice>
      </div>
    );
  }

  const timeframe = (TIMEFRAMES as readonly string[]).includes(query.timeframe ?? "")
    ? (query.timeframe as ChartTimeframe)
    : "1h";
  const candles = await getCandles(selected.id, timeframe);
  const closed = candles ? toChartData(candles) : [];
  // Stored candles are closed ones; add the one still forming, built from 5-minute candles.
  const streamed = selected.venue === "binance";
  const fiveMinute =
    streamed && closed.length > 0 ? await getCandles(selected.id, "5m", 300) : null;
  const forming = fiveMinute
    ? formingCandle(toChartData(fiveMinute), closed[closed.length - 1]?.time, SECONDS[timeframe])
    : null;
  const data = forming ? [...closed, forming] : closed;

  return (
    <div className="space-y-6">
      {heading}
      <ChartControls instruments={instruments} instrumentId={selected.id} timeframe={timeframe} />
      {candles === null ? (
        <Notice title="Could not load candles">Try again in a moment.</Notice>
      ) : data.length === 0 ? (
        <Notice title={`No ${timeframe} candles for ${selected.symbol} yet`}>
          They appear after the next update job or a backfill.
        </Notice>
      ) : (
        <Card className="p-2 sm:p-4">
          <LiveChart
            data={data}
            timeframe={timeframe}
            symbol={selected.symbol}
            streamed={streamed}
          />
        </Card>
      )}
    </div>
  );
}
