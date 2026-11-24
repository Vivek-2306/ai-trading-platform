import { StatusPill } from "@/components/status-pill";
import { Card, CardTitle } from "@/components/ui/card";
import type { DataQuality } from "@/lib/api";

function problems(item: DataQuality["instruments"][number]): string {
  if (item.candles === 0) return "No data yet";
  const found: string[] = [];
  if (item.stale) found.push("stale");
  if (item.missing_candles) found.push(`${item.missing_candles} missing`);
  if (item.inconsistent_candles) found.push(`${item.inconsistent_candles} inconsistent`);
  if (item.spikes) found.push(`${item.spikes} price spikes`);
  return found.length ? found.join(", ") : `${item.candles} candles, no problems`;
}

export function DataQualityCard({ quality }: { quality: DataQuality | null }) {
  return (
    <Card>
      <CardTitle>Market data</CardTitle>
      {quality === null ? (
        <p className="mt-3 text-sm text-muted">Quality report unavailable.</p>
      ) : (
        <ul className="mt-3 divide-y divide-border/40">
          {quality.instruments.map((item) => (
            <li
              key={`${item.venue}:${item.symbol}:${item.timeframe}`}
              className="flex flex-wrap items-center justify-between gap-2 py-2"
            >
              <div>
                <span className="font-medium">{item.symbol}</span>{" "}
                <span className="text-sm text-muted">{item.timeframe}</span>
                <p className="text-sm text-muted">{problems(item)}</p>
              </div>
              <StatusPill ok={item.ok} label={item.ok ? "Healthy" : "Check"} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
