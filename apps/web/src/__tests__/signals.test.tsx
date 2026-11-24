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
