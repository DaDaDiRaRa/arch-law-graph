"""조문 임베딩 사전계산 — graph.json 조문 → Voyage 임베딩 → data/embeddings.npy.

벡터 RAG(의미검색)용. 런타임(rag_engine)은 이 파일을 로드해 코사인 top_k 검색.
빌드 1회 실행(로컬). graph.json 갱신 시 재실행 권장.

실행 (루트에서, .env 에 VOYAGE_API_KEY 필요):
  D:\\APPS\\arch-law-diagnose\\backend\\.venv\\Scripts\\python.exe builder/build_embeddings.py

산출물:
  data/embeddings.npy       — float16 정규화 행렬 (N × dim)
  data/embeddings_meta.json — {model, dim, ids:[...], built_at 제외}
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import voyageai
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GRAPH = ROOT / "data" / "graph.json"
OUT_NPY = ROOT / "data" / "embeddings.npy"
OUT_META = ROOT / "data" / "embeddings_meta.json"

MODEL = os.getenv("VOYAGE_MODEL", "voyage-3-large")
DIM = int(os.getenv("VOYAGE_DIM", "1024"))
BATCH = 64                 # 텍스트 수(토큰캡 120K 안전)
MAX_CHARS = 1600           # 조문당 임베딩 입력 길이 상한


def article_text(n: dict) -> str:
    """임베딩 입력 텍스트 — 법령명 + 제목 + 본문(상한)."""
    law = n.get("law_nm", "")
    title = n.get("title", "")
    content = n.get("content", "") or ""
    return f"{law} {title}\n{content}"[:MAX_CHARS]


def main() -> None:
    key = os.getenv("VOYAGE_API_KEY")
    if not key:
        sys.exit("✗ VOYAGE_API_KEY 미설정 (.env 확인) — Voyage 임베딩 불가")

    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    arts = [
        n for n in g["nodes"]
        if n.get("type") == "article" and n.get("content") and len(n["content"]) > 30
    ]
    print(f"[임베딩] 조문 {len(arts):,}개 · 모델 {MODEL} · {DIM}d")

    vo = voyageai.Client(api_key=key)
    vecs: list[list[float]] = []
    ids: list[str] = []
    t0 = time.time()
    for i in range(0, len(arts), BATCH):
        chunk = arts[i:i + BATCH]
        texts = [article_text(n) for n in chunk]
        for attempt in range(5):
            try:
                r = vo.embed(texts, model=MODEL, input_type="document",
                             output_dimension=DIM, truncation=True)
                break
            except Exception as e:
                wait = 2 ** attempt
                print(f"  ⚠ 배치 {i} 재시도({attempt+1}/5) {wait}s — {e}")
                time.sleep(wait)
        else:
            sys.exit(f"✗ 배치 {i} 5회 실패 — 중단(기존 파일 보존)")
        vecs.extend(r.embeddings)
        ids.extend(n["id"] for n in chunk)
        done = i + len(chunk)
        if done % (BATCH * 8) == 0 or done == len(arts):
            print(f"  {done:,}/{len(arts):,}  ({time.time()-t0:.0f}s)")

    mat = np.asarray(vecs, dtype=np.float32)
    # L2 정규화 → 런타임은 내적만으로 코사인
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = (mat / norms).astype(np.float16)

    np.save(OUT_NPY, mat)
    OUT_META.write_text(json.dumps(
        {"model": MODEL, "dim": DIM, "count": len(ids), "ids": ids},
        ensure_ascii=False), encoding="utf-8")
    print(f"OK {OUT_NPY.name} {mat.shape} ({mat.nbytes/1e6:.1f}MB) + {OUT_META.name}")


if __name__ == "__main__":
    main()
