import { Card } from "@/components/ui/card";
import type { Signal, SignalAction } from "@/lib/api";
import { cn } from "@/lib/utils";

const ACTION: Record<SignalAction, { label: string; style: string; meaning: string }> = {
  BUY: {
    label: "BUY",
    style: "bg-good/15 text-good",
    meaning: "Conditions favour holding or entering long.",
  },
  SELL: {
    label: "SELL",
    style: "bg-bad/15 text-bad",
    meaning: "Conditions favour exiting or staying out.",
  },
  HOLD: {
    label: "HOLD",
    style: "bg-foreground/10 text-foreground",
    meaning: "Nothing decisive either way.",
  },
  NO_TRADE: {
    label: "NO TRADE",
    style: "bg-accent/15 text-accent",
    meaning: "Skip: too little data, too volatile, indicators disagree, or agreement is weak.",
  },
};

const DIRECTION_DOT: Record<string, string> = {
  buy: "bg-good",
  sell: "bg-bad",
  neutral: "bg-muted",
  info: "bg-accent",
};

export function ActionBadge({ action }: { action: SignalAction }) {
  const info = ACTION[action];
  return (
    <span
      title={info.meaning}
      className={cn(
        "inline-flex whitespace-nowrap rounded-full px-3 py-1 text-sm font-semibold",
        info.style,
      )}
    >
      {info.label}
    </span>
  );
}

export function formatCandleTime(iso: string): string {
  return `${new Date(iso).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

/** One signal with its agreement score and the reasons behind it. */
export function SignalCard({ signal }: { signal: Signal }) {
  const agreement = Math.round(Number(signal.confidence) * 100);
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{signal.symbol}</h3>
          <p className="text-sm text-muted">
            {signal.timeframe} candle · {formatCandleTime(signal.candle_ts)}
          </p>
        </div>
        <ActionBadge action={signal.action} />
      </div>

      <div className="mt-4">
        <div className="flex justify-between text-sm text-muted">
          <span>Agreement</span>
          <span className="tabular-nums">{agreement}%</span>
        </div>
        <div
          role="progressbar"
          aria-label="Agreement of the rules with the leading side"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={agreement}
          className="mt-1 h-2 overflow-hidden rounded-full bg-foreground/10"
        >
          <div className="h-full rounded-full bg-accent" style={{ width: `${agreement}%` }} />
        </div>
      </div>

      <details className="mt-4 group">
        <summary className="cursor-pointer text-sm font-medium text-accent">
          Why? ({signal.reasons.length} {signal.reasons.length === 1 ? "reason" : "reasons"})
        </summary>
        <ul className="mt-3 space-y-2">
          {signal.reasons.map((reason) => (
            <li key={reason.code} className="flex gap-2 text-sm">
              <span
                aria-hidden
                className={cn(
                  "mt-1.5 size-2 shrink-0 rounded-full",
                  DIRECTION_DOT[reason.direction] ?? "bg-muted",
                )}
              />
              <span>{reason.text}</span>
            </li>
          ))}
        </ul>
      </details>
    </Card>
  );
}
