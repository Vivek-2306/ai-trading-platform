import { resolve } from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// One env file for the whole repo: read it from the monorepo root, not from apps/web.
loadEnvConfig(resolve(import.meta.dirname, "../.."));

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  transpilePackages: ["@aitp/api-client"],
  serverExternalPackages: ["pino", "pino-pretty"],
};

export default config;
