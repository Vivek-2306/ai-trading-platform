import { afterEach, describe, expect, it, vi } from "vitest";
import { getSystemStatus } from "@/lib/api";

// Outside a real request there are no headers to read.
vi.mock("next/headers", () => ({ headers: async () => new Headers({ "x-request-id": "req-1" }) }));

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

/** Stand in for the API at the network boundary, so the real typed client is exercised. */
function stubApi(ready: Response) {
  vi.stubGlobal("fetch", async (request: Request) =>
    new URL(request.url).pathname === "/version"
      ? json({ name: "trading-api", version: "0.1.0", git_sha: null, environment: "test" })
      : ready,
  );
}

describe("getSystemStatus", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reports ready when every check is ok", async () => {
    stubApi(json({ status: "ready", checks: { database: "ok", redis: "ok" } }));
    expect(await getSystemStatus()).toMatchObject({ api: "up", ready: true, version: "0.1.0" });
  });

  it("reads the checks from a 503 response", async () => {
    stubApi(json({ status: "not_ready", checks: { database: "ok", redis: "unavailable" } }, 503));
    expect(await getSystemStatus()).toMatchObject({
      api: "up",
      ready: false,
      checks: { redis: "unavailable" },
    });
  });

  it("reports down when the API cannot be reached", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("fetch failed");
    });
    expect(await getSystemStatus()).toEqual({ api: "down" });
  });
});
