import { ChartControls, type ChartTimeframe, TIMEFRAMES } from "@/components/chart-controls";
import { LiveChart } from "@/components/live-chart";
import { Card } from "@/components/ui/card";
import { getCandles, getInstruments } from "@/lib/api";
import { toChartData } from "@/lib/chart-data";

export const dynamic = "force-dynamic";

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
  const data = candles ? toChartData(candles) : [];

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
            streamed={selected.venue === "binance"}
          />
        </Card>
      )}
    </div>
  );
}
