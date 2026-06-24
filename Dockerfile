# ── 1단계: 정적 빌드 (Vite) ───────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
# 의존성 먼저 (캐시 활용)
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci
# 소스 + graph.json (web 이 ../../data/graph.json 을 import)
COPY web/ ./web/
COPY data/ ./data/
RUN cd web && npm run build

# ── 2단계: nginx 정적 서빙 ────────────────────────────────────────────────
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/web/dist /usr/share/nginx/html
# Cloud Run 은 기본 8080 포트로 트래픽 전달
EXPOSE 8080
