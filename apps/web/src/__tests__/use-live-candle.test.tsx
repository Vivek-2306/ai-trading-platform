import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLiveCandle } from "@/components/use-live-candle";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static CLOSED = 2;
  readyState = 1;
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
  emit(close: string) {
    const data = JSON.stringify({
      ts: "2026-01-01T10:00:00Z",
      open: "1",
      high: "2",
      low: "1",
      close,
    });
    this.listeners.get("candle")?.({ data } as MessageEvent<string>);
  }
}

function Probe({ symbol }: { symbol: string | null }) {
  const { candle, status } = useLiveCandle(symbol);
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="close">{candle ? candle.close : "none"}</span>
    </div>
  );
}

describe("useLiveCandle", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("is only live once a candle has arrived, and goes quiet when they stop", () => {
    render(<Probe symbol="BTC/USDT" />);
    expect(screen.getByTestId("status")).toHaveTextContent("connecting");

    act(() => FakeEventSource.instances[0]?.emit("7"));
    expect(screen.getByTestId("status")).toHaveTextContent("live");
    expect(screen.getByTestId("close")).toHaveTextContent("7");

    act(() => vi.advanceTimersByTime(31_000));
    expect(screen.getByTestId("status")).toHaveTextContent("reconnecting");
  });

  it("retries by itself when the browser gives up on a refused connection", () => {
    render(<Probe symbol="BTC/USDT" />);
    const first = FakeEventSource.instances[0];
    if (!first) throw new Error("no stream opened");
    first.readyState = FakeEventSource.CLOSED;
    act(() => first.onerror?.());
    expect(screen.getByTestId("status")).toHaveTextContent("reconnecting");

    act(() => vi.advanceTimersByTime(5000));
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  it("never shows one symbol's price under another", () => {
    const { rerender } = render(<Probe symbol="BTC/USDT" />);
    act(() => FakeEventSource.instances[0]?.emit("7"));
    expect(screen.getByTestId("close")).toHaveTextContent("7");

    rerender(<Probe symbol={null} />);
    expect(screen.getByTestId("close")).toHaveTextContent("none");
    expect(FakeEventSource.instances[0]?.closed).toBe(true);

    rerender(<Probe symbol="ETH/USDT" />);
    expect(screen.getByTestId("close")).toHaveTextContent("none");
  });
});
