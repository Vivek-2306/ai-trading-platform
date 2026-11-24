import { resolve } from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// One env file for the whole repo: read it from the monorepo root, not from apps/web.
loadEnvConfig(resolve(import.meta.dirname, "../.."));

// The browser only talks to this web server; it forwards /api/* to the backend.
// That keeps one public URL (needed for the phone tunnel) and avoids CORS.
const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default config;
