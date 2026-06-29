import json
from pathlib import Path
from dotenv import load_dotenv

# .env 는 프로젝트 루트에 있음
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .rag_engine import RAGEngine

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
