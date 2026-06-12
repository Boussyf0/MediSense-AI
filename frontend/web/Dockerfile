# Multi-stage Dockerfile for the Next.js dashboard.
# Build stage compiles the production bundle; runtime stage runs `next start`.
FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# Next.js inlines NEXT_PUBLIC_* at build time. .env.production is gitignored
# (not in the build context), so the API base must come from the platform: DO
# passes build-time spec env vars as build args — surface it to `next build`.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

# Runtime user (Next.js doesn't need root)
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

COPY --from=builder /app/package.json /app/package-lock.json* ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./

USER nextjs
EXPOSE 3000
CMD ["npm", "start"]
