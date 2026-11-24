import { resolve } from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// One env file for the whole repo: read it from the monorepo root, not from apps/web.
loadEnvConfig(resolve(import.meta.dirname, "../.."));

const config: NextConfig = {
  reactStrictMode: true,
  // The phone/tablet tunnel builds into its own folder, so a `next dev` or `next build` run
  // for development can never overwrite the files the tunnel's server is serving.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  // Self-contained server for the Docker image; traced from the repo root (monorepo).
  output: "standalone",
  outputFileTracingRoot: resolve(import.meta.dirname, "../.."),
  poweredByHeader: false,
  transpilePackages: ["@aitp/api-client"],
  serverExternalPackages: ["pino", "pino-pretty"],
};

export default config;
