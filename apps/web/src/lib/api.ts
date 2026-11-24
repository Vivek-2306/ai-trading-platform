import { createApiClient } from "@aitp/api-client";
import { headers } from "next/headers";
import { env } from "@/lib/env";
import { logger } from "@/lib/logger";
import { safeRequestId } from "@/lib/proxy-target";

/** Server-side client: talks to the API directly (the browser goes through /api). */
export function serverApi() {
  return createApiClient(env().API_URL);
}

export type SystemStatus =
  | {
      api: "up";
      version: string;
      environment: string;
      checks: Record<string, "ok" | "unavailable">;
      ready: boolean;
    }
  | { api: "down" };

export async function getSystemStatus(): Promise<SystemStatus> {
  const client = serverApi();
  const requestId = safeRequestId((await headers()).get("x-request-id"));
  const init = {
    cache: "no-store" as const,
    headers: requestId ? { "x-request-id": requestId } : {},
  };
  try {
    const [ready, version] = await Promise.all([
      client.GET("/health/ready", { ...init, signal: AbortSignal.timeout(4000) }),
      client.GET("/version", { ...init, signal: AbortSignal.timeout(4000) }),
    ]);
    // /health/ready answers 503 with the same body when a dependency is down.
    const body = ready.data ?? (ready.error as { checks?: Record<string, "ok" | "unavailable"> });
    if (!body?.checks || !version.data) return { api: "down" };
    return {
      api: "up",
      version: version.data.version,
      environment: version.data.environment,
      checks: body.checks,
      ready: Object.values(body.checks).every((c) => c === "ok"),
    };
  } catch (error) {
    logger.warn({ request_id: requestId, err: String(error) }, "api_unreachable");
    return { api: "down" };
  }
}

export type DataQuality = {
  ok: boolean;
  instruments: {
    venue: string;
    symbol: string;
    timeframe: string;
    ok: boolean;
    candles: number;
    latest: string | null;
    missing_candles: number;
    stale: boolean;
    inconsistent_candles: number;
    spikes: number;
  }[];
};

/** Market-data quality report, or null if the API or database cannot answer. */
export async function getDataQuality(): Promise<DataQuality | null> {
  const requestId = safeRequestId((await headers()).get("x-request-id"));
  try {
    const { data } = await serverApi().GET("/data/quality", {
      cache: "no-store",
      headers: { "x-request-id": requestId },
      signal: AbortSignal.timeout(8000),
    });
    return data ?? null;
  } catch (error) {
    logger.warn({ request_id: requestId, err: String(error) }, "data_quality_unavailable");
    return null;
  }
}

export type MarketInstrument = {
  id: number;
  venue: string;
  symbol: string;
  asset_class: string;
  active: boolean;
};

export type Candle = {
  ts: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
};

/** Instruments we hold candles for, or null if the API cannot answer. */
export async function getInstruments(): Promise<MarketInstrument[] | null> {
  const requestId = safeRequestId((await headers()).get("x-request-id"));
  try {
    const { data } = await serverApi().GET("/data/instruments", {
      cache: "no-store",
      headers: { "x-request-id": requestId },
      signal: AbortSignal.timeout(6000),
    });
    return data ?? null;
  } catch (error) {
    logger.warn({ request_id: requestId, err: String(error) }, "instruments_unavailable");
    return null;
  }
}

/** The newest candles (oldest first), or null if the API cannot answer. */
export async function getCandles(
  instrumentId: number,
  timeframe: "1m" | "5m" | "1h" | "1d",
  limit = 500,
): Promise<Candle[] | null> {
  const requestId = safeRequestId((await headers()).get("x-request-id"));
  try {
    const { data } = await serverApi().GET("/data/candles", {
      params: { query: { instrument_id: instrumentId, timeframe, limit } },
      cache: "no-store",
      headers: { "x-request-id": requestId },
      signal: AbortSignal.timeout(8000),
    });
    return data?.candles ?? null;
  } catch (error) {
    logger.warn({ request_id: requestId, err: String(error) }, "candles_unavailable");
    return null;
  }
}

export type SignalReason = {
  code: string;
  text: string;
  direction: "buy" | "sell" | "neutral" | "info" | string;
  weight: number;
};

export type SignalAction = "BUY" | "SELL" | "HOLD" | "NO_TRADE";

export type SignalRisk = {
  /** False for signals from before the risk engine: not risk-assessed, do not act on them. */
  assessed: boolean;
  /** What the rules said before the risk veto (a refused BUY reads BUY here). */
  rules_action: SignalAction | null;
  kill_switch: boolean;
  vetoes: { code: string; text: string }[];
  /** Exact decimal strings. Only present for a BUY that passed the veto. */
  plan: {
    entry: string;
    stop: string;
    target: string;
    risk_per_unit: string;
    reward_per_unit: string;
    risk_reward: string;
  } | null;
  size: {
    quantity: string;
    notional: string;
    risk_amount: string;
    capital_share_pct: string;
    limited_by: string;
  } | null;
};

export type Signal = {
  id: number;
  instrument_id: number;
  symbol: string;
  venue: string;
  timeframe: string;
  candle_ts: string;
  action: SignalAction;
  /** How much of the rule weight agrees with the leading side, 0 to 1 (a decimal string). */
  confidence: string;
  reasons: SignalReason[];
  inputs: Record<string, number | null>;
  rule_version: string;
  created_at: string;
  /** The candle is old (the feed or the job stopped): do not act on this signal. */
  stale?: boolean;
  risk?: SignalRisk;
  /** BUY or SELL that passed the risk veto and is not stale. */
  actionable?: boolean;
};

/** The newest signal per instrument and timeframe, or null if the API cannot answer. */
export async function getLatestSignals(): Promise<Signal[] | null> {
  const requestId = safeRequestId((await headers()).get("x-request-id"));
  try {
    const { data } = await serverApi().GET("/signals/latest", {
      cache: "no-store",
      headers: { "x-request-id": requestId },
      signal: AbortSignal.timeout(6000),
    });
    return (data as Signal[] | undefined) ?? null;
  } catch (error) {
    logger.warn({ request_id: requestId, err: String(error) }, "signals_unavailable");
    return null;
  }
}

/** Recent signals, newest first, or null if the API cannot answer. */
export async function getRecentSignals(limit = 20): Promise<Signal[] | null> {
  const requestId = safeRequestId((await headers()).get("x-request-id"));
  try {
    const { data } = await serverApi().GET("/signals", {
      params: { query: { limit } },
      cache: "no-store",
      headers: { "x-request-id": requestId },
      signal: AbortSignal.timeout(6000),
    });
    return (data?.signals as Signal[] | undefined) ?? null;
  } catch (error) {
    logger.warn({ request_id: requestId, err: String(error) }, "signals_unavailable");
    return null;
  }
}

export type RiskStatus = {
  kill_switch: {
    active: boolean;
    since: string | null;
    actor: string | null;
    reason: string | null;
  };
  limits: {
    capital: string;
    risk_per_trade_pct: string;
    max_capital_share_pct: string;
    max_daily_loss_pct: string;
    max_open_positions: number;
    min_risk_reward: string;
  };
};

/** Kill switch state and the active limits, or null if the API cannot answer. Read on the
 * server only: the web proxy does not forward /risk to browsers. */
export async function getRiskStatus(): Promise<RiskStatus | null> {
  const requestId = safeRequestId((await headers()).get("x-request-id"));
  try {
    const { data } = await serverApi().GET("/risk/status", {
      cache: "no-store",
      headers: { "x-request-id": requestId },
      signal: AbortSignal.timeout(6000),
    });
    return (data as RiskStatus | undefined) ?? null;
  } catch (error) {
    logger.warn({ request_id: requestId, err: String(error) }, "risk_status_unavailable");
    return null;
  }
}
