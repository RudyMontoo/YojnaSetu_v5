# Frontend (React/Vite PWA) — Cloud Run container.
# Two stages: build the static bundle with Node, serve it with nginx. nginx
# also reverse-proxies the API/WebSocket paths to the backend Cloud Run
# services, so the app stays SINGLE-ORIGIN in prod — the httpOnly auth cookies
# (SameSite=Strict) only work same-origin, exactly like the dev vite proxy.

# ---- build stage ----
FROM node:20-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build      # -> /app/dist

# ---- serve stage ----
FROM nginx:1.27-alpine
# Backends are injected at container start (set per environment). Defaults are
# the local docker hostnames; override with the real Cloud Run service URLs.
ENV AI_SERVICE_URL=http://ai-service:8080 \
    SPRING_URL=http://spring-gateway:8080 \
    PORT=8080
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 8080
# nginx:alpine's entrypoint runs envsubst over /etc/nginx/templates/*.template
# into /etc/nginx/conf.d, substituting the ${VARS} below, then starts nginx.
CMD ["nginx", "-g", "daemon off;"]
