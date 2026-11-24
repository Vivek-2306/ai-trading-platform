# Web app (`@aitp/web`)

Next.js 16 (App Router), TypeScript strict, Tailwind v4, glass-style UI, dark and light themes.

```bash
pnpm --filter @aitp/web dev      # http://localhost:3000 (needs the API: pnpm dev from apps/api)
pnpm --filter @aitp/web test     # Vitest
```

## Configuration

One env file for the whole repo, at the repo root (copy `.env.example` to `.env`). The web app reads:

| Variable | Default | Meaning |
| --- | --- | --- |
| `API_URL` | `http://127.0.0.1:8000` | Where the web server reaches the API |
| `LOG_LEVEL` | `info` | `debug`, `info`, `warning` or `error` (shared with the API) |

Values are validated at startup (`src/lib/env.ts`); a bad value stops the app with a clear message.

## How requests flow

The browser only talks to this server. `/api/*` is forwarded to the API by `src/proxy.ts`, so there
is one public URL (which the phone tunnel needs) and no CORS. Every request gets an `x-request-id`;
the same ID shows up in the web log and the API log.

## Logs

pino: readable in development, JSON in production. Secrets (`token`, `password`, `authorization`, …)
are redacted.
