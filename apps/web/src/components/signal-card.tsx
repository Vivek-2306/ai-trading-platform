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
  const time = new Date(iso);
  if (Number.isNaN(time.getTime())) return "unknown time";
  return `${time.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

const money = (value: string) =>
  Number(value).toLocaleString("en-US", { maximumFractionDigits: 8 });

/** The risk engine's plan for a BUY: where to enter, stop, target, how much, and the risk. */
export function RiskPlan({ signal }: { signal: Signal }) {
  const { plan, size } = signal.risk ?? { plan: null, size: null };
  if (!plan || !size || signal.stale) return null;
  const rows: [string, string][] = [
    ["Entry", money(plan.entry)],
    ["Stop-loss", money(plan.stop)],
    ["Target", money(plan.target)],
    ["Size", `${money(size.quantity)} (${money(size.notional)} USDT)`],
    ["Risking", `${money(size.risk_amount)} USDT`],
    ["Risk : reward", `1 : ${plan.risk_reward}`],
  ];
  return (
    <section className="mt-4 rounded-xl bg-foreground/5 p-3" aria-label="Risk plan">
      <p className="text-sm font-medium">Risk plan (checked by the risk engine)</p>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="text-right tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Why the risk engine refused a BUY, or that an old signal was never risk-assessed. */
export function RiskNotes({ signal }: { signal: Signal }) {
  const risk = signal.risk;
  if (!risk) return null;
  if (!risk.assessed) {
    return (
      <p role="note" className="mt-3 text-sm text-muted">
        Not risk-assessed: this signal is from before the risk engine. Do not act on it.
      </p>
    );
  }
  if (risk.vetoes.length === 0) return null;
  return (
    <div role="note" className="mt-3 rounded-xl bg-bad/10 p-3 text-sm">
      <p className="font-medium text-bad">
        {risk.kill_switch
          ? "Kill switch is on: nothing is actionable."
          : risk.rules_action && risk.rules_action !== "NO_TRADE"
            ? `The rules said ${risk.rules_action}; the risk engine vetoed it:`
            : "The risk engine refused:"}
      </p>
      <ul className="mt-1 list-disc pl-5">
        {risk.vetoes.map((veto) => (
          <li key={veto.code}>{veto.text}</li>
        ))}
      </ul>
    </div>
  );
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
        {signal.stale ? (
          <span className="inline-flex whitespace-nowrap rounded-full bg-foreground/10 px-3 py-1 text-sm font-semibold text-muted">
            STALE
          </span>
        ) : (
          <ActionBadge action={signal.action} />
        )}
      </div>

      {signal.stale && (
        <p role="note" className="mt-3 text-sm text-bad">
          This signal is out of date (last action was {ACTION[signal.action].label}). The data feed
          or the signal job may have stopped. Do not act on it.
        </p>
      )}

      <RiskPlan signal={signal} />
      <RiskNotes signal={signal} />

      <div className={cn("mt-4", signal.stale && "opacity-50")}>
        <div className="flex justify-between text-sm text-muted">
          <span>Rule agreement with the leading side</span>
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
