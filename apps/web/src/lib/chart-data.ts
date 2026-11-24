import type { Candle } from "@/lib/api";

export type ChartCandle = {
  time: number; // seconds since the epoch, UTC
  open: number;
  high: number;
  low: number;
  close: number;
};

/**
 * API prices are exact decimal strings; the chart needs numbers. That is fine for drawing,
 * and nothing here is used to size or place an order. Bad rows are dropped, order is kept.
 */
export function toChartData(candles: Candle[]): ChartCandle[] {
  const out: ChartCandle[] = [];
  let lastTime = Number.NEGATIVE_INFINITY;
  for (const c of candles) {
    const time = Math.floor(Date.parse(c.ts) / 1000);
    const row = {
      time,
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
    };
    const finite = Object.values(row).every(Number.isFinite);
    if (!finite || time <= lastTime) continue; // the chart needs strictly increasing times
    lastTime = time;
    out.push(row);
  }
  return out;
}
