import Link from "next/link";
import type { MarketInstrument } from "@/lib/api";
import { cn } from "@/lib/utils";

export const TIMEFRAMES = ["1h", "1d"] as const;
export type ChartTimeframe = (typeof TIMEFRAMES)[number];

const pill = (active: boolean) =>
  cn(
    "rounded-full px-3 py-1.5 text-sm transition-colors",
    active ? "bg-accent/20 font-medium text-foreground" : "text-muted hover:text-foreground",
  );

/** Instrument and timeframe pickers. Plain links, so they work without JavaScript. */
export function ChartControls({
  instruments,
  instrumentId,
  timeframe,
}: {
  instruments: MarketInstrument[];
  instrumentId: number;
  timeframe: ChartTimeframe;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
      <nav aria-label="Instrument" className="flex flex-wrap gap-1">
        {instruments.map((i) => (
          <Link
            key={i.id}
            href={`/charts?instrument=${i.id}&timeframe=${timeframe}`}
            aria-current={i.id === instrumentId ? "page" : undefined}
            className={pill(i.id === instrumentId)}
          >
            {i.symbol}
          </Link>
        ))}
      </nav>
      <nav aria-label="Timeframe" className="flex gap-1">
        {TIMEFRAMES.map((tf) => (
          <Link
            key={tf}
            href={`/charts?instrument=${instrumentId}&timeframe=${tf}`}
            aria-current={tf === timeframe ? "page" : undefined}
            className={pill(tf === timeframe)}
          >
            {tf}
          </Link>
        ))}
      </nav>
    </div>
  );
}
