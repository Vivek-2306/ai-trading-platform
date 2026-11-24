# Progress

**Last updated:** 2026-11-24 (laptop)

## Current phase

**Phase 9b — Scalping strategy research** on `phase-9b-scalping` (AITP-75 … 80). Phases 7 to 9 merged (PRs #16 to #20).
v0.1.0 released 2026-11-24. Later phases (10 to 12) are planned in `docs/PLAN.md`.
Tickets: 75 fee tiers and maker/taker model, 76 scalping strategies (rules only, fixed parameters), 77 backtests on
1m/5m with walk-forward and one out-of-sample judgement each, 78 cost-drag analysis, 79 scalping risk limits
(max trades per day, cooldown), 80 research report and go/no-go.

Phase 9 result to remember: `rules-v2` does not beat buy-and-hold (hourly loses ~25 to 28% after costs; daily
is roughly flat). The locked out-of-sample period for the swing rules is still unspent (owner's decision).

## Last completed

- Setup Step 0 (answers) and Step 1 (prerequisites: git, gh as `Vivek-2306`, Node 24.1, pnpm 9.15,
  Python 3.13.3, uv 0.13.9, Docker 28.2.2, Notion) ✅
- Git repo initialised on `main` (no commits yet); GitHub repo created, public:
  https://github.com/Vivek-2306/ai-trading-platform ; remote `origin` set.
- Owner drafted `infra/docker-compose.dev.yml` (to be finalised in AITP-12).
- Notion set up: project page, Phases DB (6 rows), Tickets DB (35 tickets, views: Board,
  By phase, Blocked / Needs decision), Decisions page. Links in `CLAUDE.md`.
- `docs/PLAN.md` written with all six setup phases.
- Local git-ignored `private/` folder created for personal notes.
- Planning docs, ADR 0001 (stack, proposed) and ADR 0002 (Docker Compose, accepted).

- Owner said "go" (stack approved, ADR 0001 Accepted). First commit `bbd94fc` on `develop`;
  `main` created at the same commit; `develop` is GitHub's default branch.
- Phase 1: AITP-1 monorepo root (`d680fa6`), AITP-2 README/CHANGELOG/.env.example (`9e17c0a`),
  AITP-3 GitHub templates (`9e2932e`), AITP-4 Claude settings + format hook (`ef0bf7c`),
  AITP-5 slash commands.

- Phase 1 merged (PR #1). Branch protection on `main` and `develop` since 2026-11-23.
- Phase 2: AITP-6 Python project in `apps/api` (uv, Python 3.13, core deps, module layout).
- AITP-7 Ruff/mypy strict/pytest+coverage, wired into root `pnpm` scripts; format hook
  proved working on a `.py` edit.
- AITP-8 FastAPI `create_app()` factory, settings, `/health`, `/version`, `/docs`; 10 tests, 100% coverage of app code.
- AITP-9 structlog (JSON in prod), X-Request-ID middleware, consistent JSON errors; 24 tests.
- AITP-10 Dockerfile (`1423cb4`): image builds (263 MB), container answers `/health` and
  `/version`, runs as non-root `app`, JSON logs. (Docker Desktop needed the owner's macOS
  password once.)
- AITP-11 CI workflow (`.github/workflows/ci.yml`, job "API (Python)"), with image smoke test.
- Self-review fixes applied (headers on errors, no input echo, CORS wildcard rejected, 500s logged,
  JSON-only prod logs); 34 tests.

- Phase 2 merged (PR #2). "API (Python)" is a required check on `main` and `develop`.
- Phase 3: AITP-12 dev Compose stack (TimescaleDB 2.32 + pgvector 0.8 verified, Redis 7), `pnpm infra:*`.
- AITP-13 async SQLAlchemy engine/sessions, `Base` naming conventions, `/health/ready` (verified 200 against dev DB, 503 when down); 41 tests.
- AITP-14 Alembic + baseline migration `0001` (timescaledb, vector); upgrade/downgrade/upgrade verified on dev DB and from the image; 44 tests.
- AITP-15 async Redis client + readiness check (live: 200 → 503 when Redis stopped → 200); 46 tests.
- AITP-16 Celery app + `ping`/`heartbeat` tasks, beat schedule; live round-trip through Redis verified; 51 tests.
- AITP-17 integration tests (5) with testcontainers, in CI; dev DB image switched to pinned `timescale/timescaledb:2.32.1-pg17`.
- Self-review fixes (`%` in DB passwords, startup cleanup, Celery visibility timeout and no redelivery loops, heartbeat results off, `pnpm beat` on fresh clones); 53 unit + 5 integration tests.

- Phase 3 merged (PR #3, `892f48f`). Phase 4 started: AITP-18 Next.js 16 app in `apps/web` (strict TS, `/api/*` proxied to the API, repo-root env file loaded).
- AITP-19 responsive glass UI shell (Tailwind v4, dark/light, bottom nav on phones), AITP-20 Biome + Vitest, AITP-21 `packages/api-client` generated from OpenAPI (CI checks it is fresh), AITP-22 live system status page (API/DB/Redis; verified Redis down → shows Down), AITP-36 validated env + pino logs + one request ID across web and API logs, AITP-37 `pnpm tunnel` (ngrok; verified from the public URL), AITP-23 web CI job. 10 web tests.

- Phase 4 merged (PR #4). Phase 4b: AITP-39 Postman collection generated from OpenAPI (`pnpm api:postman`, CI checks it), AITP-38 Notion API Reference database (5 rows) + CLAUDE.md rule 12, AITP-40 log redaction, quiet health probes, optional `LOG_FILE` and `SENTRY_DSN`; 61 API tests.

- Phase 4b merged (PR #5). Phase 5: uv groups `analysis` (pandas, NumPy, Polars, SciPy, statsmodels, TA-Lib, vectorbt, QuantStats, exchange-calendars), `ml` (scikit-learn, LightGBM, Optuna, MLflow, SHAP), `ai` (anthropic, voyageai, pgvector) + AI settings, `markets` (kiteconnect, ccxt, alpaca-py, polygon, finnhub, fredapi, feedparser, trafilatura, python-telegram-bot, websockets, tenacity); smoke tests + CI job; Dependabot. Findings: exchange-calendars has BSE (`XBOM`) but no NSE calendar; LightGBM needs `brew install libomp` on macOS (Linux image needs libgomp1, Phase 6). QuantStats pulls in yfinance (Yahoo scraping: fine for experiments, not a production data source); MLflow is the lightweight `mlflow-skinny` client, telemetry off in CI (`MLFLOW_DISABLE_TELEMETRY=true`; set it locally too).

- Phase 5 merged (PR #6). Phase 6: AITP-30 pre-commit hooks (`pnpm hooks:install`), AITP-31 gitleaks in CI (full history clean), AITP-32 production Compose (web, API, worker, beat, db, redis, Caddy; verified locally, only Caddy exposed), AITP-33 quickstart verified from a fresh clone (`pnpm bootstrap`, `pnpm check`), AITP-34 branch protection script (4 required checks; `main` not strict so release PRs cannot deadlock), AITP-35 setup report + CHANGELOG 0.1.0.

- Phase 7 (crypto and gold market data): AITP-41 candle tables (hypertable, NUMERIC, UTC), AITP-42 Binance adapter via ccxt, AITP-43 gold: PAXG/USDT default plus optional Twelve Data XAU/USD, AITP-44 backfill job, AITP-45 hourly update + market-hours-aware gap refill, AITP-46 data-quality checks + `/data/quality` + status page card, AITP-47 `/data/instruments` and `/data/candles`, AITP-48 web `/charts`. Verified live with real Binance data (BTC, ETH, PAXG all healthy). Review fixes: Twelve Data "no data" handling, throttling, NY-time market hours, key never in errors.

## In progress

Phase 9b is implemented (AITP-75 to 80); self-review and PR next.

Phase 9b result: **no-go**. All 12 strategy/instrument/timeframe combinations lose money out of sample
(profit factor 0.01 to 0.30); average gross move per trade is about zero or negative before the ~20 bps
round-trip fee, so the rules have no edge. Details in `docs/SCALPING_RESEARCH.md`. Scalping locks are spent;
the swing lock is untouched.

## Next up

1. Phase 9b in progress; the owner reviews and merges its PR when opened.
   Owner decision pending: whether to judge the swing rules' locked out-of-sample period (`docs/BACKTESTING.md`).
2. Owner: add to `.env.example` (Claude cannot edit it): `API_URL`, `POSTGRES_PORT`, `REDIS_PORT`, `LOG_FILE`, `SENTRY_DSN`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`; later the gold data API key.
3. Owner decision: narrow the over-broad `Bash(* .env.*)` deny rule.
4. Review Dependabot PRs #7 to #10; do not merge #11 (TypeScript 7 breaks the API client generator).

Feature order: 7 data → 7b live stream → 8a signals → 8b risk → 9 backtest → 9b scalping research → 10 ML → 11 news/AI → 12 paper trading.

## Owner decisions (answered 2026-11-24)

- [x] Personal tool only (no SEBI registration or data resale concerns for now; revisit if it ever goes public).
- [x] MVP market: crypto first; Indian markets later.
- [x] Indian broker: undecided, not urgent (only needed when Indian markets start).
- [x] Hosting: a single server is enough; develop everything on Docker with free tiers, move to cloud plans later.
- [x] Budget: near zero during development (free tiers + local Docker); paid plans only when moving to a server.
- [x] Mobile app: after the web app.

## Known issues

- Phase 9b limitations (deliberate, review-found): the backtest cooldown starts at the exit candle's open time
  (about one candle shorter than configured); the daily trade cap counts an entry on its fill candle's UTC day
  but checks on the decision candle's day (can exceed by one at midnight); the code fingerprint omits
  `backtest/costs.py`, `risk/limits.py` and `scalping/research.py`. Not changed, because the scalping locks are spent
  and the result (no-go) is far from any of these margins.

- Phase 8a limitations (deliberate, to revisit): the signals trigger guards against mistakes but the table owner
  can still disable it (a non-owner app role would fix that); a candle corrected by the REST overwrite after its
  signal was stored leaves that signal's inputs slightly out of step (rare; the close is stored for comparison);
  `GET /signals` orders by recorded id, not candle time; rules-v1 thresholds are untested guesses until Phase 9
  backtests measure them; a long uptrend often reads as NO TRADE because RSI/Bollinger rules disagree with trend.

- Phase 7b limitations (deliberate, to revisit): quiet minutes on thin symbols (e.g. PAXG) have no 1m candle
  at all (Binance sends none), so the gap check reports them and the healer refetches them every 5 minutes;
  the stream heartbeat is global (one busy symbol keeps it fresh); the SSE stream limit is global (50), not
  per client; migration `0003` is not atomic (the aggregates are created outside a transaction, so a failed
  run needs a manual fix); the ngrok tunnel was not re-tested because another tunnel (pid 65021) was
  already running on this laptop.

- Phase 7 limitations (deliberate, to revisit): exchange holidays for spot gold (Dec 25, Jan 1) show as
  candle gaps and are re-fetched hourly; the chart shows only the newest 500 candles (no scroll-back yet);
  `/data/quality` is uncached; the Twelve Data adapter has never been called live (needs a free key, then
  check that an old `start_date` with `order=ASC` returns the oldest rows).

- Old dev volume `aitp_db-data` (from the previous timescaledb-ha image) is unused; the owner
  can delete it with `docker volume rm aitp_db-data` (it only held an empty dev database).

- Non-Claude prices in `docs/COSTS.md` are approximate and were not verified live.

## Session log

| Date | Env | Summary |
| --- | --- | --- |
| 2026-11-23 | laptop | Setup answers, prerequisites, plan doc, project memory files, Docker Compose decision |
| 2026-11-23 | laptop | GitHub repo created; Notion phases/tickets DBs + 35 tickets; PLAN.md; working mode → Claude implements, owner reviews PRs |
| 2026-11-23 | laptop | Branching → develop/main; first commit on develop; Phase 1 (AITP-1 … 5) implemented, PR opened |
