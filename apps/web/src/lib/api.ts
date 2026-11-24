import { createApiClient } from "@aitp/api-client";

/** Server-side client: talks to the API directly (the browser goes through /api). */
export function serverApi() {
  return createApiClient(process.env.API_URL ?? "http://127.0.0.1:8000");
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
  try {
    const [ready, version] = await Promise.all([
      client.GET("/health/ready", { cache: "no-store", signal: AbortSignal.timeout(4000) }),
      client.GET("/version", { cache: "no-store", signal: AbortSignal.timeout(4000) }),
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
  } catch {
    return { api: "down" };
  }
}
