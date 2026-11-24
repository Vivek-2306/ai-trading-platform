import type { ChartCandle } from "@/lib/chart-data";

export type LiveCandle = { time: number; open: number; high: number; low: number; close: number };

/** Parses one `candle` event from the stream. Returns null for anything malformed. */
export function parseLiveCandle(raw: string): LiveCandle | null {
  try {
    const v = JSON.parse(raw) as Record<string, string>;
    const candle = {
      time: Math.floor(Date.parse(v.ts ?? "") / 1000),
      open: Number(v.open),
      high: Number(v.high),
      low: Number(v.low),
      close: Number(v.close),
    };
    return Object.values(candle).every(Number.isFinite) ? candle : null;
  } catch {
    return null;
  }
}

/**
 * Folds a live 1-minute candle into the chart's current candle of size `seconds`. If the live
 * minute belongs to a newer period, a new candle starts. Updates for older periods are ignored.
 * Returns the candle to draw, or null if there is nothing to change.
 */
export function applyLive(
  last: ChartCandle | undefined,
  live: LiveCandle,
  seconds: number,
): ChartCandle | null {
  const bucket = Math.floor(live.time / seconds) * seconds;
  if (!last || bucket > last.time) {
    return { time: bucket, open: live.open, high: live.high, low: live.low, close: live.close };
  }
  if (bucket < last.time) return null;
  return {
    time: last.time,
    open: last.open,
    high: Math.max(last.high, live.high),
    low: Math.min(last.low, live.low),
    close: live.close,
  };
}
