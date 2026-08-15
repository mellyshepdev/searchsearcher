# Multi-stage: the build toolchain (typescript, eslint, tailwind, @types/*)
# is needed to compile but never to serve, so it stays out of the final image.

# ── deps ──────────────────────────────────────────────────────────────
# Full install, dev dependencies included — `next build` needs them.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── builder ───────────────────────────────────────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# drizzle.config.ts throws unless DATABASE_URL is set, and it is imported
# during the build. The app's pg pool is lazy (see src/db/index.ts), so a
# placeholder gets us through `next build` without a live database.
ENV DATABASE_URL=postgresql://placeholder:placeholder@localhost:5432/placeholder
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── runner ────────────────────────────────────────────────────────────
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# `output: "standalone"` emits server.js plus a traced node_modules holding
# only the packages the server actually imports.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# No drizzle-kit here on purpose. It is a devDependency, and installing it into
# the runtime image both failed to resolve drizzle-orm and dragged ~680MB of npm
# cache along. The schema push now runs as a one-shot `migrate` service built
# from the `builder` stage above, which already has the CLI and the full
# dependency tree — see docker-compose.yml.
EXPOSE 3000
CMD ["node", "server.js"]
