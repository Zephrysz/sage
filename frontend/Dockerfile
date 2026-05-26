# Stage 1: Install dependencies
FROM node:20-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# Stage 2: Development (hot reload)
FROM deps AS development
WORKDIR /app

COPY . .

EXPOSE 3000
ENV NODE_ENV=development
CMD ["npm", "run", "dev"]

# Stage 3: Build for production
FROM deps AS builder
WORKDIR /app

COPY . .

ENV NODE_ENV=production
RUN npm run build

# Stage 4: Production runtime
FROM node:20-alpine AS production
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
