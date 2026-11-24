import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DataQualityCard } from "@/components/data-quality";
import { getDataQuality } from "@/lib/api";

vi.mock("next/headers", () => ({ headers: async () => new Headers({ "x-request-id": "req-1" }) }));

const item = {
  venue: "binance",
  symbol: "BTC/USDT",
  timeframe: "1h",
  ok: true,
  candles: 720,
  latest: "2026-01-01T00:00:00Z",
  missing_candles: 0,
  stale: false,
  inconsistent_candles: 0,
  spikes: 0,
};

describe("DataQualityCard", () => {
  it("shows a healthy instrument", () => {
    render(<DataQualityCard quality={{ ok: true, instruments: [item] }} />);
    expect(screen.getByText("BTC/USDT")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("720 candles, no problems")).toBeInTheDocument();
  });

  it("lists what is wrong", () => {
    const bad = { ...item, ok: false, stale: true, missing_candles: 3, spikes: 1 };
    render(<DataQualityCard quality={{ ok: false, instruments: [bad] }} />);
    expect(screen.getByText("stale, 3 missing, 1 price spikes")).toBeInTheDocument();
    expect(screen.getByText("Check")).toBeInTheDocument();
  });

  it("says when there is no data and when the report is unavailable", () => {
    const empty = { ...item, ok: false, candles: 0 };
    const { rerender } = render(<DataQualityCard quality={{ ok: false, instruments: [empty] }} />);
    expect(screen.getByText("No data yet")).toBeInTheDocument();
    rerender(<DataQualityCard quality={null} />);
    expect(screen.getByText("Quality report unavailable.")).toBeInTheDocument();
  });
});

describe("getDataQuality", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns the report", async () => {
    const body = { ok: true, instruments: [item] };
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    expect(await getDataQuality()).toEqual(body);
  });

  it("returns null when the API is unreachable", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("fetch failed");
    });
    expect(await getDataQuality()).toBeNull();
  });
});
