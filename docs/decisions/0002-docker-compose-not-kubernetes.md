# ADR 0002: Docker Compose for early stages, not Kubernetes

- Status: Accepted (owner asked for a recommendation; low development budget)
- Date: 2026-11-23

## Context

The owner wants minimal spend during development and asked whether to use Docker or
Kubernetes early on. The MVP is one user, a handful of processes (API, workers, stream
service, Postgres + TimescaleDB, Redis) and fits on one server.

## Decision

- **Local development:** Docker Compose runs only the stateful services (Postgres +
  TimescaleDB, Redis). The API and web app run natively (`uv run`, `pnpm dev`) for fast
  hot reload. Cost: $0.
- **MVP and beta:** the same Compose file, extended with the API, worker and stream
  containers, on one ~$48/mo server (two at beta), behind Caddy.
- **Kubernetes:** not now. Revisit only when one of these is true: several servers must
  scale workers automatically, uptime needs rolling deploys across machines, or a team
  beyond one person operates it. Even then, compare managed containers (AWS ECS Fargate,
  Fly.io) first; they give most of the benefit with far less operating work.

## Consequences

- Near-zero dev cost; one file describes the whole stack; easy for one person to run.
- No automatic failover or autoscaling on a single server; acceptable for paper trading and
  a small beta, with daily backups.
- Images built for Compose move unchanged to ECS or Kubernetes later.
- Kubernetes would add ≈ $73/mo for an EKS control plane (or free on DigitalOcean/Linode),
  at least 2–3 nodes, plus a lot of YAML, ingress, cert and upgrade work.
