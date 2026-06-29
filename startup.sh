#!/bin/sh
# Cloud Run 단일 컨테이너: uvicorn(8001) + nginx(8080) 동시 실행
set -e
cd /app
# uvicorn 기동 실패 시 traceback 이 즉시 로그로 flush 되도록(버퍼링 해제).
# 미설정 시 import 단계 크래시의 traceback 이 유실되어 502 원인 파악 불가.
export PYTHONUNBUFFERED=1
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --workers 1 &
nginx -g "daemon off;"
