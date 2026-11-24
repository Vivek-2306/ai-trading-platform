# syntax=docker/dockerfile:1
# Web app image. Build from the REPO ROOT (it is a pnpm workspace):
#   docker build -f apps/web/Dockerfile -t aitp-web .

ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-slim AS builder
RUN corepack enable
WORKDIR /repo
# Dependency manifests first, so code changes don't invalidate the install layer.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/api-client/package.json packages/api-client/
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --filter @aitp/web...
COPY apps/web apps/web
COPY packages/api-client packages/api-client
COPY biome.json ./
RUN pnpm --filter @aitp/web build

FROM node:${NODE_VERSION}-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN groupadd --system app && useradd --system --gid app --no-create-home app
# Standalone output keeps the monorepo layout: the server lives at apps/web/server.js.
COPY --from=builder --chown=app:app /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=app:app /repo/apps/web/.next/static ./apps/web/.next/static
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["node", "apps/web/server.js"]
