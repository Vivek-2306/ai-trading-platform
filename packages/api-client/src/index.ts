import createClient from "openapi-fetch";
import type { paths } from "./schema";

export type { components, paths } from "./schema";

/** Typed API client. `baseUrl` is "/api" in the browser (proxied by the web server). */
export function createApiClient(baseUrl: string) {
  return createClient<paths>({ baseUrl });
}

export type ApiClient = ReturnType<typeof createApiClient>;
