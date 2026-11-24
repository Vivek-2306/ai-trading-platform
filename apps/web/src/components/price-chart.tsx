"use client";

import type { ISeriesApi, UTCTimestamp } from "lightweight-charts";
import { CandlestickSeries, ColorType, createChart } from "lightweight-charts";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";
import type { ChartCandle } from "@/lib/chart-data";
import { applyLive, type LiveCandle } from "@/lib/live";

const UP = "#22c55e";
const DOWN = "#ef4444";

/** A candlestick chart that fills its container and follows the light/dark theme. */
export function PriceChart({
  data,
  live = null,
  timeframeSeconds = 3600,
}: {
  data: ChartCandle[];
  live?: LiveCandle | null;
  timeframeSeconds?: number;
}) {
  const container = useRef<HTMLDivElement>(null);
  const series = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const current = useRef<ChartCandle | undefined>(undefined);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const dark = resolvedTheme !== "light";
    const chart = createChart(element, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: dark ? "#cbd5e1" : "#334155",
      },
      grid: {
        vertLines: { color: dark ? "rgba(148,163,184,0.12)" : "rgba(51,65,85,0.1)" },
        horzLines: { color: dark ? "rgba(148,163,184,0.12)" : "rgba(51,65,85,0.1)" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
      borderVisible: false,
    });
    candles.setData(data.map((c) => ({ ...c, time: c.time as UTCTimestamp })));
    series.current = candles;
    current.current = data[data.length - 1];
    chart.timeScale().fitContent();
    return () => {
      series.current = null;
      chart.remove();
    };
  }, [data, resolvedTheme]);

  // A live update moves the newest candle (or starts the next one) without redrawing the chart.
  useEffect(() => {
    if (!live || !series.current) return;
    const next = applyLive(current.current, live, timeframeSeconds);
    if (!next) return;
    current.current = next;
    series.current.update({ ...next, time: next.time as UTCTimestamp });
  }, [live, timeframeSeconds]);

  const first = data[0];
  const last = data[data.length - 1];
  const summary =
    first && last
      ? `Candlestick price chart, ${data.length} candles from ${new Date(first.time * 1000).toISOString().slice(0, 10)} to ${new Date(last.time * 1000).toISOString().slice(0, 10)}, last close ${last.close}`
      : "Candlestick price chart";

  return (
    <div ref={container} role="img" aria-label={summary} className="h-[55dvh] min-h-72 w-full" />
  );
}
