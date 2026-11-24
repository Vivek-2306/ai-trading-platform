import { type NextRequest, NextResponse } from "next/server";
import { env } from "@/lib/env";
import { logger } from "@/lib/logger";

/**
 * Runs for every request: gives it a request ID (kept if the caller sent one), logs it, and
 * forwards /api/* to the backend with the same ID so one request can be followed across both logs.
 */
export function proxy(request: NextRequest) {
  const requestId = request.headers.get("x-request-id") ?? crypto.randomUUID();
  const headers = new Headers(request.headers);
  headers.set("x-request-id", requestId);

  const { pathname, search } = request.nextUrl;
  logger.info({ request_id: requestId, method: request.method, path: pathname }, "request");

  const response = pathname.startsWith("/api/")
    ? NextResponse.rewrite(new URL(pathname.slice("/api".length) + search, env().API_URL), {
        request: { headers },
      })
    : NextResponse.next({ request: { headers } });
  response.headers.set("x-request-id", requestId);
  return response;
}

export const config = {
  // Skip static assets.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
