/** Only these API paths may be reached from the browser (and so from the public tunnel). */
export const ALLOWED_API_PATHS = new Set(["/health", "/health/ready", "/version"]);

const REQUEST_ID = /^[A-Za-z0-9._-]{1,128}$/;

/** Keeps a caller's request ID only if it is safe to log; otherwise makes a new one. */
export function safeRequestId(value: string | null): string {
  return value && REQUEST_ID.test(value) ? value : crypto.randomUUID();
}

/**
 * Maps a web path like `/api/health` to the API URL, or returns null if it is not allowed.
 * The path is matched exactly against the allowlist, so `//host`, `\host` or encoded
 * tricks can never change the destination host.
 */
export function apiTarget(pathname: string, apiUrl: string): URL | null {
  if (!pathname.startsWith("/api/")) return null;
  const path = pathname.slice("/api".length);
  if (!ALLOWED_API_PATHS.has(path)) return null;
  const target = new URL(apiUrl);
  target.pathname = path;
  return target;
}
