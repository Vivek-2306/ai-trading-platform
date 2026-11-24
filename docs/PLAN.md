# Plan

Source of truth for scope. Notion is the source of truth for status
(Tickets DB: https://app.notion.com/p/421426f94e2f817ba5d5d4591d2b4b3c).
Full acceptance criteria live in each Notion ticket; the summary here must stay in sync.

Phase size rule: 5–8 tickets, roughly ≤600 changed lines per PR; split bigger phases (3a/3b).
One branch and one PR per phase, cut from and merged into `develop`. The owner reviews
tickets and PRs and merges. Releases go `develop` → `main` by PR (first one at v0.1.0).

## Setup phases (foundation, before feature work) — planned 2026-11-23

### Phase 1 — Repo foundation and workflow (`phase-1-repo-foundation`)

**Goal:** monorepo skeleton, project docs, GitHub templates, Claude Code settings and commands.

- AITP-1 Monorepo root workspace: pnpm workspace, Turborepo, root scripts, `.editorconfig`, `.nvmrc`, `.python-version`, folders
- AITP-2 Repo docs: README, CHANGELOG, `.env.example`, git-ignored local `private/` folder
- AITP-3 GitHub templates: PR template, issue templates, CODEOWNERS
- AITP-4 Claude Code `.claude/settings.json` (allow/deny) + format hook
- AITP-5 Claude Code slash commands (8 workflow commands)

**Out of scope:** any Python or web app code.

### Phase 2 — Backend API skeleton (`phase-2-api-skeleton`)

**Goal:** FastAPI app in `apps/api` with health endpoints, tooling, Dockerfile and Python CI.

- AITP-6 Python project in `apps/api` with uv (core deps only, module layout)
- AITP-7 Ruff, mypy strict, pytest + coverage; wired into root scripts
- AITP-8 FastAPI app factory, settings, `/health`, `/version`, OpenAPI
- AITP-9 Structured logging, request IDs, consistent error responses
- AITP-10 API Dockerfile (multi-stage, non-root, healthcheck)
- AITP-11 CI workflow: Python job

**Out of scope:** database, workers, trading logic.

### Phase 3 — Local infrastructure and data layer (`phase-3-data-layer`)

**Goal:** Compose dev stack and the async data layer.

- AITP-12 Dev Compose: TimescaleDB (+pgvector) and Redis, healthchecks, `pnpm infra:*` scripts
- AITP-13 Async SQLAlchemy 2 engine/sessions, `/health/ready` checks DB
- AITP-14 Alembic + baseline migration enabling `timescaledb` and `vector`
- AITP-15 Redis client, readiness check per dependency, 503 when down
- AITP-16 Celery worker + beat skeleton (`ping`, heartbeat)
- AITP-17 Integration tests with real Postgres and Redis (testcontainers), run in CI

**Out of scope:** market-data tables and ingestion.

### Phase 4 — Web app skeleton (`phase-4-web-skeleton`)

**Goal:** Next.js shell talking to the API through a typed client.

- AITP-18 Next.js app in `apps/web` (TS strict)
- AITP-19 Tailwind + shadcn/ui app shell: responsive (phone, tablet, desktop), modern glass UI (translucent blurred panels), dark mode
- AITP-20 Biome + `tsc` + Vitest/Testing Library, wired into Turborepo
- AITP-21 `packages/api-client` generated from OpenAPI; CI fails if stale
- AITP-22 System status page (API, DB, Redis)
- AITP-23 CI workflow: web job
- AITP-36 Web env and logging: one root `.env` read by web and API (validated), pino logs with request IDs
- AITP-37 ngrok dev tunnel: `pnpm tunnel` serves the web app at a public URL for phone and tablet checks

**Out of scope:** real dashboards, charts, auth. Mobile app deferred.

### Phase 4b — API reference, Postman and logging (`phase-4b-api-docs`)

**Goal:** every API endpoint documented in Notion and Postman, and logs that are easy to search.

- AITP-38 Notion "API Reference" database: one row per endpoint with method, path, auth, request, response, errors, status
- AITP-39 Postman collection generated from the OpenAPI schema (`docs/api/`); CI fails if stale; new endpoints must update it
- AITP-40 Logging hardening: request/response logs, redaction of secrets, rotating log files, optional Sentry hook (off by default)

### Phase 5 — Domain packages and dependency management (`phase-5-domain-deps`)

**Goal:** every package the features need, installed and smoke-tested.

- AITP-24 `analysis` group: pandas, NumPy, Polars, TA-Lib, SciPy, statsmodels, vectorbt, QuantStats, exchange-calendars
- AITP-25 `ml` group: scikit-learn, LightGBM, Optuna, MLflow, SHAP
- AITP-26 `ai` group: anthropic, voyageai, pgvector + settings fields
- AITP-27 `markets` group: kiteconnect, ccxt, alpaca-py, polygon-api-client, finnhub-python, fredapi, feedparser, trafilatura, python-telegram-bot, websockets, tenacity (no OANDA for now)
- AITP-28 Import smoke tests for every package, in CI
- AITP-29 Dependabot for uv, npm, Actions, Docker

**Out of scope:** using the packages.

### Phase 6 — Quality gates, deploy base and v0.1.0 (`phase-6-quality-deploy`)

**Goal:** safety nets, a deployable Compose stack, and the first release.

- AITP-30 Pre-commit hooks (Ruff, Biome, gitleaks, whitespace)
- AITP-31 Secret scanning (gitleaks) in CI
- AITP-32 Full-stack Compose for the MVP server (api, worker, beat, db, redis, Caddy)
- AITP-33 Developer commands + quickstart verified from a fresh clone
- AITP-34 Branch protection on main via `gh api`
- AITP-35 Release v0.1.0 and setup report

**Out of scope:** provisioning a real server (needs the hosting decision).

## Feature phases — planned 2026-11-24

Owner decisions: personal tool; crypto + gold first, Indian markets later; swing/position
trading first, scalping researched right after backtesting; spot, long-only, no leverage;
Docker + free tiers in development; web first, then mobile. See ADR 0003.
Ticket numbers continue from AITP-41; Notion tickets are created by `/start-phase`.

### Phase 7 — Crypto and gold market data (`phase-7-market-data`)

**Goal:** clean candles for BTC/USDT, ETH/USDT and gold stored in TimescaleDB and charted on the web app.

- AITP-41 Instrument and candle tables: hypertable, UTC, `NUMERIC` prices; supports 1m to 1d. AC: migration up/down works; duplicates rejected; prices round-trip as `Decimal`.
- AITP-42 Exchange adapter interface + Binance public adapter (`ccxt`, no key). AC: contract tests on recorded fixtures with no network; retries rate-limit errors with backoff; closed candles only.
- AITP-43 Gold data source spike + adapter: compare free sources for XAU/USD (e.g. Twelve Data) vs `PAXG/USDT`; build the chosen adapter. AC: decision and free-tier limits recorded in ADR 0003; adapter passes the same contract tests; API key via env only.
- AITP-44 Historical backfill job (Celery). AC: loads N years per instrument and timeframe; idempotent re-run; progress logged.
- AITP-45 Scheduled incremental updates + gap refill, aware of market hours (crypto 24/7, gold closed weekends). AC: beat pulls new candles; gaps detected and refilled; weekend gold gap is not an error.
- AITP-46 Data-quality checks. AC: gaps, duplicates and outlier spikes reported; results shown on `/status`.
- AITP-47 API: `GET /instruments`, `GET /candles`. AC: paginated and validated; Postman and Notion API Reference updated (rule 12).
- AITP-48 Web price chart page (`lightweight-charts`). AC: responsive at phone width; loading and empty states; tested.

**Out of scope:** live streaming, indicators, other exchanges, Indian markets.

### Phase 7b — Live streaming data (`phase-7b-live-stream`)

**Goal:** real-time 1m candles for scalping research and live prices on the chart.

- AITP-49 Stream service process (Binance WebSocket via `ccxt`/`websockets`) in Compose. AC: connects, reconnects with backoff, health check.
- AITP-50 Write 1m candles to Redis (latest) and TimescaleDB (closed). AC: no duplicates after reconnect; closed candles only persisted.
- AITP-51 Gap detection and REST backfill after disconnects. AC: simulated drop is healed; gap logged.
- AITP-52 1m/5m aggregates, compression and retention policy. AC: continuous aggregates 1m→5m→1h; retention configurable; query results match raw candles.
- AITP-53 API WebSocket/SSE live price endpoint. AC: authenticated-ready design; backpressure safe; documented in Postman/Notion.
- AITP-54 Web live price on the chart. AC: updates without reload; shows disconnected state.

**Out of scope:** order execution, strategies.

### Phase 8a — Indicators and rule signals (`phase-8a-signals`)

**Goal:** explainable Buy / Sell / Hold / NO TRADE from plain rules, any timeframe.

- AITP-55 Indicator library: RSI, MACD, SMA, EMA, ATR, Bollinger, VWAP (TA-Lib). AC: values match reference data; warm-up bars handled.
- AITP-56 Feature pipeline without look-ahead. AC: a test proves no feature uses a future candle.
- AITP-57 Signals tables with append-only audit. AC: each row stores reasons and inputs; updates/deletes blocked.
- AITP-58 Rule engine. AC: outputs Buy/Sell/Hold/NO TRADE with reasons and confidence; conflicting indicators → NO TRADE.
- AITP-59 Scheduled signal run on candle close, timeframe parameter. AC: idempotent per candle.
- AITP-60 API `GET /signals`. AC: filterable by instrument and timeframe; Postman and Notion updated.
- AITP-61 Web signals page with reasons. AC: responsive; each signal explains itself.

**Out of scope:** ML, news, sizing.

### Phase 8b — Risk engine (`phase-8b-risk`)

**Goal:** no signal reaches the user without passing the risk veto.

- AITP-62 ATR stop-loss, target and risk-to-reward. AC: below-minimum R:R is vetoed; `Decimal` maths.
- AITP-63 Fixed-fractional position sizing with caps. AC: property tests; never exceeds the per-trade cap.
- AITP-64 Risk limits config (per-trade risk, daily loss, open positions). AC: conservative defaults; personal values in `private/` or env, not the repo.
- AITP-65 Veto layer. AC: every signal passes through it; veto → NO TRADE with reason; a test fails if any path bypasses it.
- AITP-66 Kill switch. AC: halts new signals; changes are audited.
- AITP-67 API and web show entry, stop, target, size, R:R. AC: Postman/Notion updated; responsive.

**Out of scope:** orders, any broker.

### Phase 9 — Backtesting (`phase-9-backtest`)

**Goal:** measure strategies honestly, any timeframe.

- AITP-68 Backtest engine on vectorbt with fees, slippage and a latency penalty as inputs. AC: reproducible results; timeframe parameter.
- AITP-69 Walk-forward splitter and locked out-of-sample period. AC: out-of-sample never used for tuning (enforced in code).
- AITP-70 Metrics: win rate, profit factor, max drawdown, Sharpe, expectancy. AC: tested on known series.
- AITP-71 Celery job and stored runs. AC: run config and results persisted; re-runnable.
- AITP-72 Leakage tests. AC: a deliberately leaky strategy is caught.
- AITP-73 Buy-and-hold benchmark comparison. AC: report shows strategy vs benchmark, net of costs.
- AITP-74 API and web report page. AC: Postman/Notion updated; responsive.

**Out of scope:** ML models, parameter tuning.

### Phase 9b — Scalping strategy research (`phase-9b-scalping`)

**Goal:** find out, net of fees, whether any 1m/5m rule strategy has an edge.

- AITP-75 Fee-tier and maker/taker cost model. AC: configurable tiers; documented assumptions.
- AITP-76 Scalping strategies: VWAP pullback, EMA scalp, range breakout (rules only). AC: each is deterministic and tested.
- AITP-77 Backtest each on 1m/5m, walk-forward, with realistic costs. AC: out-of-sample results stored.
- AITP-78 Trade-frequency and cost-drag analysis. AC: report shows gross vs net P&L and fee share.
- AITP-79 Risk-engine limits for scalping (max trades per day, cooldown after losses). AC: enforced by the veto layer.
- AITP-80 Research report and go/no-go. AC: written verdict per strategy; only strategies beating costs out-of-sample move to paper trading.

**Out of scope:** live or paper scalping, ML.

### Phase 10 — ML layer (`phase-10-ml`)

**Goal:** find out whether LightGBM probabilities beat the rules baseline out of sample on swing timeframes (1h, 1d; BTC and ETH). Ships only if they do.

- AITP-81 Labels and dataset builder. AC: label = target (1.6 ATR) hit before stop (1.0 ATR) within N candles; reuses the causal features; leakage test passes; the locked out-of-sample period is excluded.
- AITP-82 Training with purged walk-forward validation. AC: gap between train and validation avoids label overlap; runs tracked in MLflow; parameters declared in advance.
- AITP-83 Baselines and calibration. AC: compared with the rules, buy-and-hold and a coin-flip model; probabilities calibrated; Brier score reported.
- AITP-84 ML strategy in the backtest. AC: registered as `ml-lgbm-v1`; passes the leakage check; risk veto unchanged; the model only gates entries and never sizes.
- AITP-85 One out-of-sample judgement. AC: runs stored; pass rules fixed in advance (net return above 0, profit factor at least 1.2, at least 30 trades, better than the rules on the same period).
- AITP-86 Report and go/no-go. AC: generated `docs/ML_RESEARCH.md`; a failing model does not ship.

**Out of scope:** news, AI reasoning, paper trading, live signals from the model.
**Owner decision pending (at AITP-85):** spend the swing out-of-sample lock once, for both the rules and the model.

### Later phases (outline only; tickets written when they start)

- **Phase 11 — News and AI layer:** Haiku bulk news scoring, Opus final reasoning, pgvector context. The AI explains; it never sizes or places orders.
- **Phase 12 — Paper trading and alerts:** simulated trades on live prices for swing and scalping, tracked by the same metrics, Telegram alerts.
- **After that:** web polish, mobile app (Expo), Indian markets (broker decision then), optional live trading behind approval and hard limits.
