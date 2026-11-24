import { Writable } from "node:stream";
import pino from "pino";
import { describe, expect, it } from "vitest";
import { parseEnv } from "@/lib/env";
import { REDACT_PATHS } from "@/lib/logger";

describe("parseEnv", () => {
  it("applies defaults", () => {
    expect(parseEnv({})).toMatchObject({ API_URL: "http://127.0.0.1:8000", LOG_LEVEL: "info" });
  });

  it("rejects a bad URL with a readable message", () => {
    expect(() => parseEnv({ API_URL: "not a url" })).toThrow(/API_URL/);
  });

  it("rejects an unknown log level", () => {
    expect(() => parseEnv({ LOG_LEVEL: "loud" })).toThrow(/LOG_LEVEL/);
  });
});

describe("log redaction", () => {
  it("hides secrets but keeps normal fields", () => {
    let line = "";
    const sink = new Writable({
      write(chunk, _enc, done) {
        line += chunk.toString();
        done();
      },
    });
    const log = pino({ redact: { paths: REDACT_PATHS, censor: "[redacted]" } }, sink);

    log.info({ token: "abc123", user: { password: "hunter2" }, path: "/status" }, "x");

    expect(line).not.toContain("abc123");
    expect(line).not.toContain("hunter2");
    expect(line).toContain("/status");
  });
});
