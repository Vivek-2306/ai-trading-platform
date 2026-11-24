import pino from "pino";
import { env } from "@/lib/env";

/** Keys whose values must never reach a log line. */
export const REDACT_PATHS = [
  "authorization",
  "cookie",
  "password",
  "token",
  "api_key",
  "*.authorization",
  "*.cookie",
  "*.password",
  "*.token",
  "*.api_key",
];

export function createLogger(level: string, pretty: boolean) {
  return pino({
    name: "web",
    level: level === "warning" ? "warn" : level,
    redact: { paths: REDACT_PATHS, censor: "[redacted]" },
    base: { service: "web" },
    timestamp: pino.stdTimeFunctions.isoTime,
    formatters: { level: (label) => ({ level: label }) },
    ...(pretty ? { transport: { target: "pino-pretty", options: { colorize: true } } } : {}),
  });
}

const { LOG_LEVEL, NODE_ENV } = env();

/** JSON in production (for log tools), readable in development. */
export const logger = createLogger(LOG_LEVEL, NODE_ENV === "development");
