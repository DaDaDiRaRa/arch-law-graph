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
