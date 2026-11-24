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
