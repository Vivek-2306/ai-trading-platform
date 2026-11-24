import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveChart } from "@/components/live-chart";
import { applyLive, formingCandle, parseLiveCandle } from "@/lib/live";

const HOUR = 3600;
const at = (iso: string) => Math.floor(Date.parse(iso) / 1000);

describe("parseLiveCandle", () => {
  it("reads a stream event", () => {
    const raw = JSON.stringify({
      ts: "2026-01-01T10:05:00+00:00",
      open: "100",
      high: "102.5",
      low: "99",
      close: "101.25",
      volume: "3",
    });
    expect(parseLiveCandle(raw)).toEqual({
      time: at("2026-01-01T10:05:00Z"),
      open: 100,
      high: 102.5,
      low: 99,
      close: 101.25,
    });
  });

  it.each(["not json", "{}", '{"ts":"x","open":"1","high":"1","low":"1","close":"1"}'])(
    "rejects %s",
    (raw) => expect(parseLiveCandle(raw)).toBeNull(),
  );
});

describe("applyLive", () => {
  const last = { time: at("2026-01-01T10:00:00Z"), open: 100, high: 105, low: 98, close: 103 };
  const minute = (iso: string, o: number, h: number, l: number, c: number) => ({
    time: at(iso),
    open: o,
    high: h,
    low: l,
    close: c,
  });

  it("moves the current candle's close and widens its range", () => {
    const next = applyLive(last, minute("2026-01-01T10:30:00Z", 103, 108, 97, 107), HOUR);
    expect(next).toEqual({ time: last.time, open: 100, high: 108, low: 97, close: 107 });
  });

  it("keeps the range when the live minute is inside it", () => {
    const next = applyLive(last, minute("2026-01-01T10:30:00Z", 103, 104, 101, 102), HOUR);
    expect(next).toEqual({ ...last, close: 102 });
  });

  it("starts a new candle when the period has rolled over", () => {
    const next = applyLive(last, minute("2026-01-01T11:02:00Z", 107, 108, 106, 107.5), HOUR);
    expect(next).toEqual({
      time: at("2026-01-01T11:00:00Z"),
      open: 107,
      high: 108,
      low: 106,
      close: 107.5,
    });
  });

  it("ignores an update for an older period", () => {
    expect(applyLive(last, minute("2026-01-01T09:59:00Z", 1, 2, 1, 2), HOUR)).toBeNull();
  });

  it("starts the first candle when there is no history", () => {
    const next = applyLive(undefined, minute("2026-01-01T10:30:00Z", 1, 2, 1, 2), HOUR);
    expect(next?.time).toBe(at("2026-01-01T10:00:00Z"));
  });
});

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readyState = 1;
  static CLOSED = 2;
  onerror: (() => void) | null = null;
  listeners = new Map<string, (e: MessageEvent<string>) => void>();
  closed = false;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: (e: MessageEvent<string>) => void) {
    this.listeners.set(name, fn);
  }
  close() {
    this.closed = true;
  }
  emit(data: string) {
    this.listeners.get("candle")?.({ data } as MessageEvent<string>);
  }
}

vi.mock("@/components/price-chart", () => ({
  PriceChart: ({ live }: { live: { close: number } | null }) => (
    <div data-testid="chart">live close: {live ? live.close : "none"}</div>
  ),
}));

describe("LiveChart", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  const data = [{ time: 1, open: 1, high: 2, low: 1, close: 1.5 }];

  it("connects to the stream, shows live status and passes updates to the chart", () => {
    const { unmount } = render(<LiveChart data={data} timeframe="1h" symbol="BTC/USDT" streamed />);
    const source = FakeEventSource.instances[0];
    expect(source?.url).toBe("/api/data/stream?symbol=BTC%2FUSDT");
    expect(screen.getByText("Connecting…")).toBeInTheDocument();

    act(() =>
      source?.emit(
        JSON.stringify({ ts: "2026-01-01T10:00:00Z", open: "1", high: "9", low: "1", close: "7" }),
      ),
    );
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByTestId("chart")).toHaveTextContent("live close: 7");
    expect(screen.getByText("7")).toBeInTheDocument();

    unmount();
    expect(source?.closed).toBe(true);
  });

  it("shows a disconnected state while the browser retries", () => {
    render(<LiveChart data={data} timeframe="1h" symbol="BTC/USDT" streamed />);
    act(() => FakeEventSource.instances[0]?.onerror?.());
    expect(screen.getByText("Reconnecting…")).toBeInTheDocument();
  });

  it("does not open a stream for instruments without a live feed", () => {
    render(<LiveChart data={data} timeframe="1d" symbol="XAU/USD" streamed={false} />);
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(screen.getByText("No live feed for this instrument")).toBeInTheDocument();
  });
});

describe("formingCandle", () => {
  const five = (iso: string, o: number, h: number, l: number, c: number) => ({
    time: at(iso),
    open: o,
    high: h,
    low: l,
    close: c,
  });
  const lastClosed = at("2026-01-01T13:00:00Z");

  it("builds the current hour from the closed 5-minute candles inside it", () => {
    const candles = [
      five("2026-01-01T13:55:00Z", 1, 2, 1, 2), // belongs to the previous hour
      five("2026-01-01T14:00:00Z", 10, 12, 9, 11),
      five("2026-01-01T14:05:00Z", 11, 15, 10, 14),
      five("2026-01-01T14:10:00Z", 14, 14.5, 8, 9),
    ];
    expect(formingCandle(candles, lastClosed, HOUR)).toEqual({
      time: at("2026-01-01T14:00:00Z"),
      open: 10,
      high: 15,
      low: 8,
      close: 9,
    });
  });

  it("returns null when that period is already stored or has no closed 5-minute candle", () => {
    const candles = [five("2026-01-01T13:55:00Z", 1, 2, 1, 2)];
    expect(formingCandle(candles, at("2026-01-01T13:00:00Z"), HOUR)).toBeNull();
    expect(formingCandle([], lastClosed, HOUR)).toBeNull();
  });
});
