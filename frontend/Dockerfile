# Multi-stage build: compile the Vite/React app, then serve the static
# output with nginx, which also reverse-proxies /api/* to the backend
# container -- the browser only ever talks to one origin (this container),
# so no CORS configuration is needed at runtime, unlike the Vite dev server
# setup (see vite.config.ts's dev-only proxy).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
    CMD wget -qO- http://localhost:80/ >/dev/null || exit 1
