# ADR 0001: Python backend, TypeScript web and mobile, one monorepo

- Status: Accepted (owner approved 2026-11-23)
- Date: 2026-11-23

## Context

The platform's core work is market data, indicators, ML models, LLM analysis, backtesting
and risk maths. It also needs a web dashboard with trading charts and a mobile app for
alerts and trade approvals. One developer (with Claude Code) builds it.

## Decision

- Backend: Python 3.13 + FastAPI, Celery + Redis, PostgreSQL + TimescaleDB + pgvector.
- Web: Next.js (TypeScript). Mobile: Expo / React Native (TypeScript), added in a later phase.
- One repo: `apps/api`, `apps/web`, `apps/mobile`, `packages/*`; uv + pnpm workspaces.
- Full package list: `docs/TECH_STACK.md`.

## Consequences

- Direct access to Python's data/ML/backtesting ecosystem; no wrappers.
- Two languages to maintain; mitigated by generating the TS API client from FastAPI's OpenAPI spec.
- Web and mobile share types, API client and logic.
- TimescaleDB rules out AWS RDS later (use Timescale Cloud or self-managed).
