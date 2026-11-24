"use client";

import { PriceChart } from "@/components/price-chart";
import { StatusPill } from "@/components/status-pill";
import { useLiveCandle } from "@/components/use-live-candle";
import type { ChartCandle } from "@/lib/chart-data";

const SECONDS = { "1h": 3600, "1d": 86400 } as const;

/** The price chart plus a live connection badge and the latest price. */
export function LiveChart({
  data,
  timeframe,
  symbol,
  streamed,
}: {
  data: ChartCandle[];
  timeframe: keyof typeof SECONDS;
  symbol: string;
  /** Only instruments the stream service follows have a live feed. */
  streamed: boolean;
}) {
  const { candle, status } = useLiveCandle(streamed ? symbol : null);
  const last = candle?.close ?? data[data.length - 1]?.close;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-2 sm:px-0">
        <div aria-live="polite" className="text-lg font-semibold tabular-nums">
          {last !== undefined ? last.toLocaleString("en-US", { maximumFractionDigits: 8 }) : "—"}
          <span className="ml-2 text-sm font-normal text-muted">{symbol}</span>
        </div>
        {streamed ? (
          <StatusPill
            ok={status === "live"}
            label={
              status === "live" ? "Live" : status === "connecting" ? "Connecting…" : "Reconnecting…"
            }
          />
        ) : (
          <span className="text-sm text-muted">No live feed for this instrument</span>
        )}
      </div>
      <PriceChart data={data} live={candle} timeframeSeconds={SECONDS[timeframe]} />
    </div>
  );
}
