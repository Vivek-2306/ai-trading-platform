import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BacktestCard } from "@/components/backtest-cards";
import { EquityChart } from "@/components/equity-chart";
import { type BacktestSummary, getBacktest, getBacktests } from "@/lib/api";
import { day, money, num, pct } from "@/lib/format";

vi.mock("next/headers", () => ({ headers: async () => new Headers({ "x-request-id": "req-1" }) }));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "dark" }) }));

const setData = vi.fn();
const remove = vi.fn();
vi.mock("lightweight-charts", () => ({
  ColorType: { Solid: "solid" },
  LineSeries: "line",
  createChart: () => ({
    addSeries: () => ({ setData }),
    timeScale: () => ({ fitContent: vi.fn() }),
    remove,
  }),
}));

const run = (over: Partial<BacktestSummary> = {}): BacktestSummary => ({
  id: 7,
  created_at: "2026-11-24T10:00:00Z",
  symbol: "BTC/USDT",
  timeframe: "1h",
  strategy: "rules-v2",
  segment: "tuning",
  config_hash: "abc123",
  range_start: "2022-11-24T00:00:00Z",
  range_end: "2025-06-01T00:00:00Z",
  candle_count: 24000,
  code_version: "dev",
  metrics: {
    trades: 508,
    win_rate_pct: 29.1,
    profit_factor: 0.61,
    total_return_pct: -25.3,
    max_drawdown_pct: 25.3,
    warnings: [],
  },
  benchmark: { benchmark_return_pct: 324.9, verdict: "Did not beat buy-and-hold." },
  ...over,
});

describe("format helpers", () => {
  it("handle missing values without throwing", () => {
    expect(pct(null)).toBe("n/a");
    expect(pct(undefined)).toBe("n/a");
    expect(pct(Number.NaN)).toBe("n/a");
    expect(num(null)).toBe("n/a");
    expect(money(null)).toBe("n/a");
    expect(pct(-25.27)).toBe("-25.3%");
    expect(num(0.6123)).toBe("0.61");
  });

  it("formats exact money strings without float rounding", () => {
    expect(money("1234567.891")).toBe("1,234,567.89");
    expect(money("-80.03565139938104405")).toBe("-80.03");
    expect(money("100.00")).toBe("100");
    expect(day("2026-11-24T10:00:00Z")).toBe("2026-11-24");
  });
});

describe("BacktestCard", () => {
  it("shows the headline numbers, the benchmark and a link to the details", () => {
    render(<BacktestCard run={run()} />);
    expect(screen.getByText("BTC/USDT")).toBeInTheDocument();
    expect(screen.getByText("-25.3%")).toBeInTheDocument(); // return
    expect(screen.getByText("324.9%")).toBeInTheDocument(); // buy and hold
    expect(screen.getByText("508")).toBeInTheDocument();
    expect(screen.getByText("Did not beat buy-and-hold.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Details" })).toHaveAttribute("href", "/backtests/7");
  });

  it("shows sample-size warnings", () => {
    render(
      <BacktestCard
        run={run({ metrics: { trades: 5, warnings: ["Only 5 trades: mostly noise."] } })}
      />,
    );
    expect(screen.getByRole("note")).toHaveTextContent("Only 5 trades");
  });

  it("summarises walk-forward windows instead of a single return", () => {
    render(
      <BacktestCard
        run={run({
          segment: "walk_forward",
          metrics: {
            windows: 6,
            profitable_windows: 2,
            mean_window_return_pct: -1.8,
            total_trades: 252,
          },
          benchmark: {},
        })}
      />,
    );
    expect(screen.getByText(/Walk-forward · 2022-11-24 to 2025-06-01/)).toBeInTheDocument();
    expect(screen.getByText("2/6 up")).toBeInTheDocument();
    expect(screen.getByText("-1.8%")).toBeInTheDocument();
    expect(screen.getByText("252")).toBeInTheDocument();
  });
});

describe("EquityChart", () => {
  beforeEach(() => vi.clearAllMocks());

  it("draws both curves and cleans up", () => {
    const { unmount } = render(
      <EquityChart
        curves={{
          times: ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
          strategy: [1000, 1010],
          benchmark: [1000, 1100],
        }}
      />,
    );
    expect(setData).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/Strategy 1,010/)).toBeInTheDocument();
    expect(screen.getByText(/Buy and hold 1,100/)).toBeInTheDocument();
    unmount();
    expect(remove).toHaveBeenCalled();
  });

  it("draws nothing without data", () => {
    render(<EquityChart curves={{}} />);
    expect(setData).not.toHaveBeenCalled();
  });
});

describe("fetchers", () => {
  afterEach(() => vi.unstubAllGlobals());
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

  it("lists runs", async () => {
    vi.stubGlobal("fetch", async () => json([run()]));
    expect(await getBacktests(5)).toEqual([run()]);
  });

  it("tells a missing run from an unreachable API", async () => {
    vi.stubGlobal("fetch", async () => json({ error: { code: "http_404" } }, 404));
    expect(await getBacktest(99)).toBeUndefined();
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("fetch failed");
    });
    expect(await getBacktest(1)).toBeNull();
    expect(await getBacktests()).toBeNull();
  });
});

describe("robustness", () => {
  beforeEach(() => vi.clearAllMocks());

  it("never shows a negative zero", () => {
    expect(money("-0.001")).toBe("0");
    expect(money("-0.50")).toBe("-0.5");
  });

  it("leaves out chart points it cannot draw instead of throwing", () => {
    render(
      <EquityChart
        curves={{
          times: ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "2026-01-03T00:00:00Z"],
          strategy: [1000, 1010], // one value short
          benchmark: [1000, 1100, Number.NaN],
        }}
      />,
    );
    expect(setData).toHaveBeenCalledTimes(2);
    expect(setData.mock.calls[0]?.[0]).toHaveLength(2); // the strategy line has 2 real points
    expect(setData.mock.calls[1]?.[0]).toHaveLength(2); // the NaN point is dropped
  });
});
