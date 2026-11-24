import { z } from "zod";

const schema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  // Where the web server reaches the API (browsers use the /api proxy instead).
  API_URL: z.url().default("http://127.0.0.1:8000"),
  // Same variable as the API, so one setting controls both services.
  LOG_LEVEL: z.enum(["debug", "info", "warning", "error"]).default("info"),
});

export type Env = z.infer<typeof schema>;

/** Parses and validates the environment. Fails fast with a readable message. */
export function parseEnv(source: Record<string, string | undefined>): Env {
  const result = schema.safeParse(source);
  if (!result.success) {
    const problems = result.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`);
    throw new Error(`Invalid environment:\n${problems.join("\n")}`);
  }
  return result.data;
}

let cached: Env | undefined;

export function env(): Env {
  cached ??= parseEnv(process.env);
  return cached;
}
