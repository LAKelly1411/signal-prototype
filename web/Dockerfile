# syntax=docker/dockerfile:1.7
#
# Sector Signal web: multi-stage Next.js (App Router, standalone output) build,
# following tpa-email-signatures. Build from the repo root so the image can
# carry a snapshot of data/ and config/ for local runs; on stage DATA_BASE_URL
# and CONFIG_BASE_URL point at the live files instead.
ARG NODE_VERSION=20-alpine

FROM registry.pressassociation.io/node:${NODE_VERSION} AS deps
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@10.32.0 --activate
COPY web/pnpm-lock.yaml web/package.json ./
RUN pnpm install --frozen-lockfile --ignore-scripts

FROM registry.pressassociation.io/node:${NODE_VERSION} AS builder
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@10.32.0 --activate
COPY web/ ./
COPY --from=deps /workspace/node_modules ./node_modules
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM registry.pressassociation.io/node:${NODE_VERSION} AS runner
RUN addgroup -g 1001 -S nodejs \
  && adduser -u 1001 -S -G nodejs -s /bin/sh nextjs \
  && apk add --no-cache tini
WORKDIR /app
ARG BUILD_TAG=unknown
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NEXT_TELEMETRY_DISABLED=1 \
    BUILD_TAG=${BUILD_TAG} \
    DATA_DIR=/app/data \
    CONFIG_DIR=/app/config
COPY --from=builder --chown=nextjs:nodejs /workspace/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /workspace/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /workspace/public ./public
COPY --chown=nextjs:nodejs data ./data
COPY --chown=nextjs:nodejs config ./config
USER 1001
EXPOSE 3000
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]
