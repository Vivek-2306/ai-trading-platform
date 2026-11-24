"use client";

import { useEffect, useState } from "react";
import { type LiveCandle, parseLiveCandle } from "@/lib/live";

export type LiveStatus = "connecting" | "live" | "reconnecting";

/** Follows the API's live candle stream for a symbol. The browser reconnects on its own. */
export function useLiveCandle(symbol: string | null) {
  const [candle, setCandle] = useState<LiveCandle | null>(null);
  const [status, setStatus] = useState<LiveStatus>("connecting");

  useEffect(() => {
    if (!symbol) return;
    setCandle(null);
    setStatus("connecting");
    const source = new EventSource(`/api/data/stream?symbol=${encodeURIComponent(symbol)}`);
    source.onopen = () => setStatus("live");
    source.onerror = () => setStatus("reconnecting");
    source.addEventListener("candle", (event) => {
      const parsed = parseLiveCandle((event as MessageEvent<string>).data);
      if (parsed) {
        setCandle(parsed);
        setStatus("live");
      }
    });
    return () => source.close();
  }, [symbol]);

  return { candle, status };
}
