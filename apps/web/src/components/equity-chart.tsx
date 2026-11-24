"use client";

import { ColorType, createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

type Curves = { times?: string[]; strategy?: number[]; benchmark?: number[] };

/** Strategy equity against buy-and-hold, both net of the same costs. */
export function EquityChart({ curves }: { curves: Curves }) {
  const container = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const element = container.current;
    const times = curves.times ?? [];
    if (!element || times.length === 0) return;
    const dark = resolvedTheme !== "light";
    const chart = createChart(element, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: dark ? "#cbd5e1" : "#334155",
      },
      grid: {
        vertLines: { color: dark ? "rgba(148,163,184,0.1)" : "rgba(51,65,85,0.08)" },
        horzLines: { color: dark ? "rgba(148,163,184,0.1)" : "rgba(51,65,85,0.08)" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const series = (values: number[] | undefined, color: string) => {
      const line = chart.addSeries(LineSeries, { color, lineWidth: 2, priceLineVisible: false });
      // Only real points: the chart throws on a missing value.
      line.setData(
        times.flatMap((t, i) => {
          const value = values?.[i];
          const time = Math.floor(Date.parse(t) / 1000);
          return value !== undefined && Number.isFinite(value) && Number.isFinite(time)
            ? [{ time: time as UTCTimestamp, value }]
            : [];
        }),
      );
    };
    series(curves.strategy, "#818cf8");
    series(curves.benchmark, "#94a3b8");
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [curves, resolvedTheme]);

  const last = (values?: number[]) => values?.[values.length - 1];
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        <span className="flex items-center gap-2">
          <span aria-hidden className="size-2.5 rounded-full bg-accent" />
          Strategy {last(curves.strategy)?.toLocaleString("en-US")}
        </span>
        <span className="flex items-center gap-2 text-muted">
          <span aria-hidden className="size-2.5 rounded-full bg-muted" />
          Buy and hold {last(curves.benchmark)?.toLocaleString("en-US")}
        </span>
      </div>
      <div
        ref={container}
        role="img"
        aria-label={`Equity curve: the strategy ends at ${last(curves.strategy)?.toLocaleString("en-US") ?? "n/a"}, buy and hold at ${last(curves.benchmark)?.toLocaleString("en-US") ?? "n/a"}`}
        className="h-72 w-full"
      />
    </div>
  );
}
