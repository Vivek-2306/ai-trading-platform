import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChartControls } from "@/components/chart-controls";
import { PriceChart } from "@/components/price-chart";
import { toChartData } from "@/lib/chart-data";

const setData = vi.fn();
const remove = vi.fn();
vi.mock("lightweight-charts", () => ({
  CandlestickSeries: "candles",
  ColorType: { Solid: "solid" },
  createChart: () => ({
    addSeries: () => ({ setData }),
    timeScale: () => ({ fitContent: vi.fn() }),
    remove,
  }),
}));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark" }) }));

const candle = (ts: string, close = "101.5") => ({
  ts,
  open: "100",
  high: "102",
  low: "99",
  close,
  volume: "5",
});

describe("toChartData", () => {
  it("converts decimal strings and ISO times", () => {
    expect(toChartData([candle("2026-01-01T00:00:00Z")])).toEqual([
      { time: 1767225600, open: 100, high: 102, low: 99, close: 101.5 },
    ]);
  });

  it("drops bad rows and keeps times strictly increasing", () => {
    const rows = [
      candle("2026-01-01T00:00:00Z"),
      candle("2026-01-01T00:00:00Z"), // duplicate time
      candle("2026-01-01T01:00:00Z", "not-a-number"),
      candle("2025-12-31T23:00:00Z"), // earlier than the last kept
      candle("2026-01-01T02:00:00Z"),
    ];
    expect(toChartData(rows).map((c) => c.time)).toEqual([1767225600, 1767225600 + 7200]);
  });
});

describe("PriceChart", () => {
  beforeEach(() => vi.clearAllMocks());

  it("draws the data and cleans up", () => {
    const data = toChartData([candle("2026-01-01T00:00:00Z")]);
    const { unmount } = render(<PriceChart data={data} />);
    expect(
      screen.getByRole("img", {
        name: "Candlestick price chart, 1 candles from 2026-01-01 to 2026-01-01, last close 101.5",
      }),
    ).toBeInTheDocument();
    expect(setData).toHaveBeenCalledWith(data);
    unmount();
    expect(remove).toHaveBeenCalled();
  });
});

describe("ChartControls", () => {
  const instruments = [
    { id: 1, venue: "binance", symbol: "BTC/USDT", asset_class: "crypto", active: true },
    { id: 2, venue: "binance", symbol: "ETH/USDT", asset_class: "crypto", active: true },
  ];

  it("links each instrument and timeframe and marks the current ones", () => {
    render(<ChartControls instruments={instruments} instrumentId={2} timeframe="1d" />);
    expect(screen.getByRole("link", { name: "ETH/USDT" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "BTC/USDT" })).toHaveAttribute(
      "href",
      "/charts?instrument=1&timeframe=1d",
    );
    expect(screen.getByRole("link", { name: "1d" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "1h" })).toHaveAttribute(
      "href",
      "/charts?instrument=2&timeframe=1h",
    );
  });
});
