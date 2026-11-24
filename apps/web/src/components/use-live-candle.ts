"use client";

import { useEffect, useState } from "react";
import { type LiveCandle, parseLiveCandle } from "@/lib/live";

export type LiveStatus = "connecting" | "live" | "reconnecting";

const RETRY_MS = 5000;
/** No candle for this long (the stream service is down, say) means the price is not live. */
const STALE_MS = 30_000;

/**
 * Follows the API's live candle stream for a symbol. The browser reconnects by itself after
 * a dropped connection; after a refusal (the server is full, say) it gives up, so we retry.
 * "live" means a candle arrived recently, not merely that the connection is open.
 */
export function useLiveCandle(symbol: string | null) {
  const [state, setState] = useState<{
    symbol: string;
    candle: LiveCandle | null;
    status: LiveStatus;
  } | null>(null);

  useEffect(() => {
    if (!symbol) return;
    let source: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let stale: ReturnType<typeof setTimeout> | undefined;
    let closed = false;
    const update = (patch: Partial<{ candle: LiveCandle | null; status: LiveStatus }>) =>
      setState((current) => ({
        symbol,
        candle: current?.symbol === symbol ? current.candle : null,
        status: current?.symbol === symbol ? current.status : "connecting",
        ...patch,
      }));

    const connect = () => {
      source = new EventSource(`/api/data/stream?symbol=${encodeURIComponent(symbol)}`);
      source.addEventListener("candle", (event) => {
        const parsed = parseLiveCandle((event as MessageEvent<string>).data);
        if (!parsed) return;
        update({ candle: parsed, status: "live" });
        clearTimeout(stale);
        stale = setTimeout(() => update({ status: "reconnecting" }), STALE_MS);
      });
      source.onerror = () => {
        update({ status: "reconnecting" });
        if (source?.readyState === EventSource.CLOSED && !closed) {
          retry = setTimeout(connect, RETRY_MS); // the browser will not retry a refusal
        }
      };
    };

    setState({ symbol, candle: null, status: "connecting" });
    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      clearTimeout(stale);
      source?.close();
    };
  }, [symbol]);

  // State from a previous symbol is never shown under a new one.
  const current = state && state.symbol === symbol ? state : null;
  return {
    candle: current?.candle ?? null,
    status: current?.status ?? ("connecting" as LiveStatus),
  };
}
