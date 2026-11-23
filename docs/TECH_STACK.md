# Tech stack

Status: approved 2026-11-23 (ADR 0001).

Python 3.13 for everything that touches data, AI and money; TypeScript for everything a
person looks at. One repo: uv for Python, pnpm workspaces (+ Turborepo) for TypeScript.

## Backend core (Python)

| Package | Use |
| --- | --- |
| FastAPI + Uvicorn | REST and WebSocket API; OpenAPI spec |
| Pydantic v2, pydantic-settings | Validation and typed config |
| SQLAlchemy 2 (async) + asyncpg | Database access |
| Alembic | Migrations |
| Celery + redis-py | Background jobs, scheduler (Celery Beat) |
| httpx, websockets | External APIs; live feeds |
| tenacity | Retries with backoff |
| structlog | Structured JSON logs |
| PyJWT, argon2-cffi, pyotp | Tokens, password hashing, 2FA |
| cryptography | Encrypting broker API keys at rest |

## Data, analysis and backtesting

| Package | Use |
| --- | --- |
| pandas, NumPy | Time series |
| Polars | Fast bulk transforms |
| TA-Lib | 150+ indicators and candlestick patterns |
| SciPy, statsmodels | Statistics, regime and volatility models |
| vectorbt | Fast vectorised research backtests |
| Own event-driven simulator | Realistic backtests reusing the live risk engine |
| QuantStats | Performance reports |
| exchange-calendars | Market hours and holidays |

## Machine learning and AI

| Package | Use |
| --- | --- |
| scikit-learn | Pipelines, calibration, baselines |
| LightGBM | Main prediction models |
| Optuna | Walk-forward hyperparameter tuning |
| MLflow | Experiment tracking, model registry |
| SHAP | Per-prediction explanations |
| anthropic | Claude API: Haiku 5.5 (`claude-haiku-5-5`) bulk news; Opus 5.5 (`claude-opus-5-5`) final reasoning |
| voyageai | Text embeddings |
| pgvector | Embedding storage and search |
| PyTorch | Later, only if deep models beat LightGBM |

## Market data, news and brokers

| Package | Market | Use |
| --- | --- | --- |
| kiteconnect | India (NSE, BSE, F&O, currency derivatives) | Zerodha data, ticks, orders |
| ccxt | Crypto | Binance, Coinbase, 100+ exchanges |
| alpaca-py | US stocks | Data, paper trading, orders |
| polygon-api-client | US stocks | Higher-quality US data |
| oandapyV20 | Forex (non-Indian users only; see compliance) | OANDA data and orders |
| finnhub-python | All | News, earnings, economic calendar |
| fredapi | Macro | US economic data |
| feedparser, trafilatura | News | RSS and clean article text |
| python-telegram-bot | Alerts | Telegram notifications |

## Web app

| Package | Use |
| --- | --- |
| Next.js (App Router), React | Framework |
| Tailwind CSS + shadcn/ui | Styling, components |
| lightweight-charts (TradingView) | Candlestick charts, indicators, signal markers |
| Recharts | Performance/report charts |
| TanStack Query | Server data fetching/caching |
| Zustand | Small client state |
| Zod | Validation |
| openapi-typescript + openapi-fetch | Typed API client from FastAPI |

## Mobile app (later phase)

| Package | Use |
| --- | --- |
| Expo SDK + Expo Router | iOS/Android, file-based navigation |
| NativeWind | Tailwind on mobile |
| expo-notifications | Push alerts |
| expo-secure-store | Token storage |
| expo-local-authentication | Face ID / fingerprint before approving a trade |
| react-native-wagmi-charts or WebView + lightweight-charts | Charts (decide in mobile phase) |
| EAS Build | Cloud builds, store submission |

## Tooling, testing, operations

| Tool | Use |
| --- | --- |
| uv | Python packages and venvs |
| Ruff | Python lint + format |
| mypy | Python type checks |
| pytest, pytest-asyncio, pytest-cov | Python tests |
| Hypothesis | Property tests for risk maths |
| respx, testcontainers | Mock HTTP; real Postgres in tests |
| pnpm workspaces + Turborepo | TS monorepo, cached builds |
| Biome | TS lint + format |
| Vitest, Testing Library | Web unit tests |
| Playwright | Web end-to-end |
| Jest (jest-expo) | Mobile tests |
| Docker + Compose | Local and MVP deploy |
| GitHub Actions | CI/CD |
| Caddy | Reverse proxy, automatic HTTPS |
| Sentry | Errors (backend, web, mobile) |
| Grafana Cloud or Better Stack | Logs, metrics, uptime |
| Doppler or Infisical | Secrets |
