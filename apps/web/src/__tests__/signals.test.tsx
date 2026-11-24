import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActionBadge, formatCandleTime, SignalCard } from "@/components/signal-card";
import { getLatestSignals, getRecentSignals, type Signal } from "@/lib/api";

vi.mock("next/headers", () => ({ headers: async () => new Headers({ "x-request-id": "req-1" }) }));

const signal = (over: Partial<Signal> = {}): Signal => ({
  id: 1,
  instrument_id: 1,
  symbol: "BTC/USDT",
  venue: "binance",
  timeframe: "1h",
  candle_ts: "2026-11-24T08:00:00Z",
  action: "BUY",
  confidence: "0.6923",
  reasons: [
    {
      code: "trend_up",
      text: "Fast average is above the slow one: uptrend.",
      direction: "buy",
      weight: 2,
    },
    { code: "rsi_overbought", text: "RSI is 74.0, overbought.", direction: "sell", weight: 1 },
  ],
  inputs: { rsi: 74 },
  rule_version: "rules-v1",
  created_at: "2026-11-24T09:10:00Z",
  ...over,
});

describe("SignalCard", () => {
  it("shows the action, the instrument, the candle time and the agreement score", () => {
    render(<SignalCard signal={signal()} />);
    expect(screen.getByText("BTC/USDT")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText(/1h candle · 2026-11-24 08:00 UTC/)).toBeInTheDocument();
    expect(screen.getByText("69%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: /agreement/i })).toHaveAttribute(
      "aria-valuenow",
      "69",
    );
  });

  it("explains itself with every reason", () => {
    render(<SignalCard signal={signal()} />);
    const why = screen.getByText(/Why\? \(2 reasons\)/);
    expect(why).toBeInTheDocument();
    const list = within(why.closest("details") as HTMLElement).getAllByRole("listitem");
    expect(list).toHaveLength(2);
    expect(list[0]).toHaveTextContent("uptrend");
    expect(list[1]).toHaveTextContent("overbought");
  });

  it("marks an out-of-date signal as stale instead of showing its action", () => {
    render(<SignalCard signal={signal({ stale: true })} />);
    expect(screen.getByText("STALE")).toBeInTheDocument();
    expect(screen.queryByText("BUY", { selector: "span" })).not.toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/Do not act on it/);
  });

  it("shows NO TRADE as a normal, labelled answer", () => {
    render(
      <SignalCard
        signal={signal({
          action: "NO_TRADE",
          reasons: [
            { code: "conflict", text: "Indicators disagree.", direction: "info", weight: 0 },
          ],
        })}
      />,
    );
    expect(screen.getByText("NO TRADE")).toBeInTheDocument();
    expect(screen.getByText(/Why\? \(1 reason\)/)).toBeInTheDocument();
  });
});

describe("ActionBadge", () => {
  it.each([
    ["BUY", "BUY"],
    ["SELL", "SELL"],
    ["HOLD", "HOLD"],
    ["NO_TRADE", "NO TRADE"],
  ] as const)("labels %s", (action, label) => {
    render(<ActionBadge action={action} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});

describe("formatCandleTime", () => {
  it("does not crash on a bad timestamp", () => {
    expect(formatCandleTime("not a date")).toBe("unknown time");
  });

  it("is always UTC", () => {
    expect(formatCandleTime("2026-11-24T08:00:00+00:00")).toBe("2026-11-24 08:00 UTC");
  });
});

describe("signal fetchers", () => {
  afterEach(() => vi.unstubAllGlobals());

  const json = (body: unknown) =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });

  it("reads the latest signals", async () => {
    vi.stubGlobal("fetch", async () => json([signal()]));
    expect(await getLatestSignals()).toEqual([signal()]);
  });

  it("reads recent signals from the paged response", async () => {
    vi.stubGlobal("fetch", async () => json({ signals: [signal()], next_before_id: null }));
    expect(await getRecentSignals(5)).toEqual([signal()]);
  });

  it("returns null when the API is unreachable", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("fetch failed");
    });
    expect(await getLatestSignals()).toBeNull();
    expect(await getRecentSignals()).toBeNull();
  });
});

describe("risk display", () => {
  const plan = {
    entry: "60000.5",
    stop: "58500",
    target: "63000",
    risk_per_unit: "1500.5",
    reward_per_unit: "2999.5",
    risk_reward: "2.00",
  };
  const size = {
    quantity: "0.00333",
    notional: "199.8",
    risk_amount: "5",
    capital_share_pct: "19.98",
    limited_by: "risk",
  };
  const risk = (over = {}) => ({
    assessed: true,
    rules_action: "BUY" as const,
    kill_switch: false,
    vetoes: [],
    plan,
    size,
    ...over,
  });

  it("shows entry, stop, target, size, risk and risk-to-reward for an actionable BUY", () => {
    render(<SignalCard signal={signal({ risk: risk(), actionable: true })} />);
    const box = screen.getByLabelText("Risk plan");
    expect(box).toHaveTextContent("Entry");
    expect(box).toHaveTextContent("60,000.5");
    expect(box).toHaveTextContent("Stop-loss");
    expect(box).toHaveTextContent("58,500");
    expect(box).toHaveTextContent("Target");
    expect(box).toHaveTextContent("Size");
    expect(box).toHaveTextContent("0.00333");
    expect(box).toHaveTextContent("Risking");
    expect(box).toHaveTextContent("1 : 2.00");
  });

  it("explains a vetoed BUY instead of showing a plan", () => {
    render(
      <SignalCard
        signal={signal({
          action: "NO_TRADE",
          risk: risk({
            plan: null,
            size: null,
            vetoes: [{ code: "max_open_positions", text: "3 positions are open; the limit is 3." }],
          }),
        })}
      />,
    );
    expect(screen.queryByLabelText("Risk plan")).not.toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(
      "The rules said BUY; the risk engine vetoed it:",
    );
    expect(screen.getByRole("note")).toHaveTextContent("3 positions are open");
  });

  it("says when the kill switch caused it", () => {
    render(
      <SignalCard
        signal={signal({
          action: "NO_TRADE",
          risk: risk({
            plan: null,
            size: null,
            kill_switch: true,
            vetoes: [{ code: "kill_switch", text: "The kill switch is on." }],
          }),
        })}
      />,
    );
    expect(screen.getByRole("note")).toHaveTextContent("Kill switch is on: nothing is actionable.");
  });

  it("flags an older signal as not risk-assessed and hides any plan", () => {
    render(
      <SignalCard signal={signal({ risk: risk({ assessed: false, plan: null, size: null }) })} />,
    );
    expect(screen.getByRole("note")).toHaveTextContent("Not risk-assessed");
    expect(screen.queryByLabelText("Risk plan")).not.toBeInTheDocument();
  });

  it("never shows a plan on a stale signal", () => {
    render(<SignalCard signal={signal({ stale: true, risk: risk() })} />);
    expect(screen.queryByLabelText("Risk plan")).not.toBeInTheDocument();
  });
});
