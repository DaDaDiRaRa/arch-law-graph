import json
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 는 프로젝트 루트에 있음
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .rag_engine import RAGEngine

VWORLD_KEY = os.getenv("VWORLD_API_KEY", "")
# VWorld 데이터 API는 키 발급 시 등록한 도메인의 Referer 헤더를 검사.
# 미설정 시 localhost(개발). Cloud Run 배포 시 등록 도메인으로 SERVICE_URL 설정 필요.
VWORLD_REFERER = os.getenv("SERVICE_URL", "http://localhost:8000")

# VWorld 용도지역명 → zoning.js zone.key 매핑
_ZONE_KEY_MAP = {
    "제1종전용주거지역": "1jeon",
    "제2종전용주거지역": "2jeon",
    "제1종일반주거지역": "1il",
    "제2종일반주거지역": "2il",
    "제3종일반주거지역": "3il",
    "준주거지역": "junju",
    "중심상업지역": "jungsang",
    "일반상업지역": "ilsang",
    "근린상업지역": "geunsang",
    "유통상업지역": "yutong",
    "전용공업지역": "jeongong",
    "일반공업지역": "ilgong",
    "준공업지역": "jungong",
    "보전녹지지역": "bojnok",
    "생산녹지지역": "saengnok",
    "자연녹지지역": "janok",
    "보전관리지역": "bojgwan",
    "생산관리지역": "saenggwan",
    "계획관리지역": "gyehoek",
    "농림지역": "nongrim",
    "자연환경보전지역": "jayeon",
}

app = FastAPI(title="arch-law-graph API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_engine: RAGEngine | None = None


@app.on_event("startup")
async def startup():
    global _engine
    _engine = RAGEngine()


@app.get("/api/ping")
def ping():
    return {"ok": True}


@app.get("/api/zoning")
async def lookup_zoning(address: str = Query(..., description="도로명 또는 지번 주소")):
    """주소 → VWorld API → 용도지역 + 시도/시군구 반환."""
    if not VWORLD_KEY:
        return {"error": "VWORLD_API_KEY 미설정 — .env에 추가 후 서버 재시작"}

    async with httpx.AsyncClient(timeout=10.0, headers={"Referer": VWORLD_REFERER}) as client:
        # 1. 주소 → 좌표 (도로명 우선, 실패 시 지번)
        geo = None
        diag = {"recv": address}  # 진단용 — 프로덕션 geocoding 실패 원인 추적
        for addr_type in ("road", "parcel"):
            r = await client.get(
                "https://api.vworld.kr/req/address",
                params={
                    "service": "address",
                    "request": "getcoord",
                    "version": "2.0",
                    "crs": "epsg:4326",
                    "address": address,
                    "refine": "true",
                    "simple": "false",
                    "format": "json",
                    "type": addr_type,
                    "key": VWORLD_KEY,
                },
            )
            body = r.json()
            resp = body.get("response", {})
            diag[addr_type] = {
                "status": resp.get("status"),
                "error": resp.get("error"),
                "http": r.status_code,
            }
            if resp.get("status") == "OK":
                geo = resp
                break

        if not geo:
            return {"error": "주소를 찾을 수 없습니다. 더 구체적인 주소를 입력해 주세요.", "_diag": diag}

        point = geo["result"]["point"]
        x = float(point["x"])  # 경도 (longitude)
        y = float(point["y"])  # 위도 (latitude)
        structure = geo.get("refined", {}).get("structure", {})
        sido = structure.get("level1", "")
        sigungu = structure.get("level2", "")
        refined_addr = geo.get("refined", {}).get("text", address)

        # 2. 좌표 → 용도지역 (VWorld Data API, LT_C_UQ111: 도시관리계획 용도지역)
        r2 = await client.get(
            "https://api.vworld.kr/req/data",
            params={
                "service": "data",
                "request": "GetFeature",
                "data": "LT_C_UQ111",
                "key": VWORLD_KEY,
                "format": "json",
                "size": "1",
                "page": "1",
                "geometry": "false",
                "attribute": "true",
                "crs": "EPSG:4326",
                "geomFilter": f"POINT({x} {y})",
            },
        )
        uq = r2.json()

        features = (
            uq.get("response", {})
            .get("result", {})
            .get("featureCollection", {})
            .get("features", [])
        )
        if not features:
            return {
                "x": x, "y": y,
                "sido": sido, "sigungu": sigungu,
                "address": refined_addr,
                "zone_name": None, "zone_key": None,
            }

        # LT_C_UQ111 용도지역 속성명은 uname. 한 좌표에 복수 feature 시
        # 국토계획법 용도지역(주거/상업/공업/녹지/관리/농림/자연환경)을 우선 선택.
        zone_name = ""
        for feat in features:
            uname = (feat["properties"].get("uname") or "").strip()
            if uname in _ZONE_KEY_MAP:
                zone_name = uname
                break
        if not zone_name:  # 매핑 못한 경우 첫 feature의 uname을 그대로 노출
            zone_name = (features[0]["properties"].get("uname") or "").strip()
        zone_key = _ZONE_KEY_MAP.get(zone_name)

        return {
            "x": x, "y": y,
            "sido": sido,
            "sigungu": sigungu,
            "address": refined_addr,
            "zone_name": zone_name,
            "zone_key": zone_key,
        }


class LookupRequest(BaseModel):
    queries: list[str]


@app.post("/api/lookup")
def lookup(req: LookupRequest):
    """조문명/노드id 목록 → 원문 본문 배치 조회 (외부 앱 그라운딩용).

    arch-law-diagnose 가 진단 적용 조문의 본문을 받아 LLM 환각을 막는 데 사용.
    과도한 요청 방지로 최대 50건만 처리.
    """
    return {"results": _engine.lookup(req.queries[:50])}


class ChatRequest(BaseModel):
    question: str
    selected_id: str | None = None


@app.post("/api/chat")
async def chat(req: ChatRequest):
    async def generate():
        async for chunk in _engine.answer_stream(req.question, req.selected_id):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 해제 (SSE)
        },
    )
