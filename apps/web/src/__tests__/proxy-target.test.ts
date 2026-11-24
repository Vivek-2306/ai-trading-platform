import { describe, expect, it } from "vitest";
import { apiTarget, safeRequestId } from "@/lib/proxy-target";

const API = "http://127.0.0.1:8000";

describe("apiTarget", () => {
  it("maps allowed paths to the API host", () => {
    expect(apiTarget("/api/health/ready", API)?.href).toBe("http://127.0.0.1:8000/health/ready");
    expect(apiTarget("/api/version", API)?.origin).toBe(API);
  });

  it("allows the live stream with a valid symbol and forwards nothing else", () => {
    const target = apiTarget("/api/data/stream", API, "?symbol=BTC/USDT&x=1&token=abc");
    expect(target?.href).toBe("http://127.0.0.1:8000/data/stream?symbol=BTC%2FUSDT");
  });

  it.each(["", "?symbol=", "?symbol=btc", "?symbol=../x", "?symbol=BTC/USDT/EXTRA", "?x=1"])(
    "refuses the live stream with search %j",
    (search) => {
      expect(apiTarget("/api/data/stream", API, search)).toBeNull();
    },
  );

  it("still blocks the other data endpoints", () => {
    expect(apiTarget("/api/data/candles", API, "?instrument_id=1&timeframe=1h")).toBeNull();
    expect(apiTarget("/api/data/quality", API)).toBeNull();
  });

  it.each([
    "/api//evil.com/x",
    "/api/\\evil.com",
    "/api/docs",
    "/api/openapi.json",
    "/api/health/",
    "/api/%2e%2e/version",
    "/other",
  ])("refuses %s", (path) => {
    expect(apiTarget(path, API)).toBeNull();
  });
});

describe("safeRequestId", () => {
  it("keeps a valid id", () => {
    expect(safeRequestId("trace-1.a_B")).toBe("trace-1.a_B");
  });

  it("replaces unsafe or oversized ids", () => {
    expect(safeRequestId("a\u001b[2Jfake")).not.toContain("\u001b");
    expect(safeRequestId("x".repeat(500))).toHaveLength(36);
    expect(safeRequestId(null)).toHaveLength(36);
  });
});
