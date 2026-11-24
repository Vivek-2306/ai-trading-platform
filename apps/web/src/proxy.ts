import { type NextRequest, NextResponse } from "next/server";
import { env } from "@/lib/env";
import { logger } from "@/lib/logger";
import { apiTarget, safeRequestId } from "@/lib/proxy-target";

/**
 * Runs for every request: gives it a request ID, logs it, and forwards the few allowed /api/*
 * paths to the backend with the same ID so one request can be followed across both logs.
 */
export function proxy(request: NextRequest) {
  const requestId = safeRequestId(request.headers.get("x-request-id"));
  const headers = new Headers(request.headers);
  headers.set("x-request-id", requestId);

  const { pathname } = request.nextUrl;
  logger.info({ request_id: requestId, method: request.method, path: pathname }, "request");

  let response: NextResponse;
  if (pathname.startsWith("/api/")) {
    const target = apiTarget(pathname, env().API_URL);
    if (!target) {
      response = NextResponse.json({ error: "not_found" }, { status: 404 });
    } else {
      // The API gets no browser credentials or caller-supplied forwarding headers.
      for (const name of ["cookie", "authorization", "x-forwarded-for", "x-forwarded-host"]) {
        headers.delete(name);
      }
      response = NextResponse.rewrite(target, { request: { headers } });
    }
  } else {
    response = NextResponse.next({ request: { headers } });
  }
  response.headers.set("x-request-id", requestId);
  return response;
}

export const config = {
  // Skip static assets.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
