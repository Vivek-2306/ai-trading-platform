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

/**
 * The candle of size `seconds` that is still forming, built from the 5-minute candles that
 * have already closed inside the current period. The stored candles are closed ones only, so
 * without this the first live update of a period would draw a candle that spans one minute.
 * Returns null if the current period has no closed 5-minute candle yet, or is already stored.
 */
export function formingCandle(
  fiveMinute: ChartCandle[],
  lastClosedTime: number | undefined,
  seconds: number,
): ChartCandle | null {
  const newest = fiveMinute[fiveMinute.length - 1];
  if (!newest) return null;
  const start = Math.floor(newest.time / seconds) * seconds;
  if (lastClosedTime !== undefined && start <= lastClosedTime) return null;
  const inside = fiveMinute.filter((c) => c.time >= start);
  const first = inside[0];
  if (!first) return null;
  return {
    time: start,
    open: first.open,
    high: Math.max(...inside.map((c) => c.high)),
    low: Math.min(...inside.map((c) => c.low)),
    close: newest.close,
  };
}
