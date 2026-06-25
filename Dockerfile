# ── 1단계: 정적 빌드 (Vite) ───────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci
COPY web/ ./web/
COPY data/ ./data/
RUN cd web && npm run build

# ── 2단계: Python 의존성 설치 ─────────────────────────────────────────────
FROM python:3.12-slim AS pybase
COPY backend/requirements.txt /req.txt
RUN pip install --no-cache-dir -r /req.txt

# ── 3단계: 최종 런타임 (Python + nginx) ──────────────────────────────────
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nginx && rm -rf /var/lib/apt/lists/*

# Python 패키지 복사
COPY --from=pybase /usr/local /usr/local

# 앱 코드 + 데이터 복사
WORKDIR /app
COPY backend/ ./backend/
COPY data/ ./data/

# 빌드된 정적 파일 복사
COPY --from=build /app/web/dist /usr/share/nginx/html

# nginx 설정
COPY nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default \
 && ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# 시작 스크립트
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

EXPOSE 8080
CMD ["/startup.sh"]
