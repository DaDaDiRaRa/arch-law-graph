#!/bin/sh
# Cloud Run 단일 컨테이너: uvicorn(8001) + nginx(8080) 동시 실행
set -e
cd /app
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --workers 1 &
nginx -g "daemon off;"
