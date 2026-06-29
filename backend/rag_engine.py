import json
import os
import re
from pathlib import Path

from anthropic import AsyncAnthropic

DATA_DIR = Path(__file__).parent.parent / "data"
GRAPH_PATH = DATA_DIR / "graph.json"
EMB_PATH = DATA_DIR / "embeddings.npy"
EMB_META_PATH = DATA_DIR / "embeddings_meta.json"

# 도메인 용어 정규화 — 검색 전 쿼리에 적용
_DOMAIN_NORM = {
    "건폐": "건폐율",
    "용적": "용적률",
    "일조권": "높이·일조",
    "조경면적": "조경",
    "이격거리": "대지공지",
    "비주거": "비거주",
}

_SYSTEM = """당신은 건축법규를 깊이 이해하는 전배 건축사입니다.
후배 건축사가 설계 실무에서 바로 써먹을 수 있도록 풍부하고 실질적인 답변을 제공하세요.

## 답변 원칙

1. **조문 근거 우선**: 제공된 조문에 있는 내용만 기준·수치로 인용합니다. 조문에 없으면 해당 항목은 "현재 DB에서 확인 불가"라고만 씁니다.
2. **실무 깊이**: 수치 나열이 아니라 다음을 포함합니다:
   - 적용 요건 (어떤 건물·용도·규모에 이 기준이 적용되나)
   - 예외·완화 조건 (단서 조항, 특례, 조례 위임 범위)
   - 국가법령 기준과 해당 지역 조례 기준이 다를 때 어느 쪽이 우선 적용되는지
   - 설계 또는 인허가 실무에서 자주 놓치거나 문제가 되는 부분
3. **조문 간 연계**: 여러 조문이 교차 적용될 경우 어떤 순서·기준으로 판단해야 하는지 설명합니다.
4. **인용 형식**: "건축법 시행령 제84조에 따르면…" 처럼 법령명 + 조문번호를 명시합니다.
5. **서술 스타일**: 마크다운 헤더(##) 과용 금지. 핵심 수치·조건만 굵게(**). 단락형 서술 위주로 읽기 편하게.
6. **추가 정보 금지**: 조문에 없는 출처·기관 연락처·웹사이트 언급 절대 금지.

답변 마지막 줄: "참고용 정보입니다. 실제 인허가는 담당 건축사 확인 필수."
"""


def _tokenize(text: str) -> list:
    text = text.lower()
    for k, v in _DOMAIN_NORM.items():
        text = text.replace(k, v)
    tokens = re.split(r"[\s\(\)\[\]「」『』，。·,\.!?]+", text)
    return [t for t in tokens if len(t) >= 2]


# 외부 앱이 보내는 조문명 → graph 노드 id 구성용.
# graph id 형식: "<법령명(공백포함)>/제N조". 약칭은 정식명(공백포함)으로 편다.
_LAW_ABBR = [("국토계획법", "국토의 계획 및 이용에 관한 법률")]


def _name_to_node_id(name: str):
    """조문명("건축법 시행령 제119조 (면적…)") → 노드 id("건축법 시행령/제119조").

    매칭 실패 시 None. 검색 추정은 하지 않음(틀린 조문 주입 방지) — exact only.
    """
    s = re.sub(r"\s*\([^)]*\)\s*$", "", name or "").strip()  # 끝 괄호주석 제거
    for abbr, full in _LAW_ABBR:
        s = s.replace(abbr, full)
    s = re.sub(r"(제\d+)조의(\d+)", r"\1의\2조", s)  # 제N조의M → 제N의M조(graph 형식)
    m = re.match(r"^(.+?)\s+(제\d+(?:의\d+)?조)$", s)
    if m:
        return m.group(1).strip() + "/" + m.group(2)
    return None


class RAGEngine:
    def __init__(self):
        with open(GRAPH_PATH, encoding="utf-8") as f:
            g = json.load(f)
        nodes = g.get("nodes", [])
        self._articles = [
            n for n in nodes
            if n.get("type") == "article"
            and n.get("content")
            and len(n["content"]) > 30
        ]
        self._by_id = {n["id"]: n for n in nodes}
        self._client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        # 벡터 검색(Voyage) — 임베딩 파일 + 키 + 라이브러리 모두 있어야 활성. 없으면 키워드 FTS.
        self._vec = None  # (matrix float32 normalized, [article nodes], voyage client, model, dim)
        self._init_vector()
        mode = "벡터(Voyage)" if self._vec else "키워드 FTS"
        print(f"[RAG] {len(self._articles):,}개 조문 로드 · 검색모드={mode}")

    def _init_vector(self):
        if not (EMB_PATH.exists() and EMB_META_PATH.exists() and os.environ.get("VOYAGE_API_KEY")):
            return
        try:
            import numpy as np
            import voyageai
            meta = json.loads(EMB_META_PATH.read_text(encoding="utf-8"))
            mat = np.load(EMB_PATH).astype(np.float32)  # 이미 L2 정규화됨
            ids = meta["ids"]
            if mat.shape[0] != len(ids):
                print("[RAG] 임베딩 행수≠ids — 벡터 비활성"); return
            # ids → 현재 graph 노드. 누락 행은 제외(graph 변경 대비).
            rows, arts = [], []
            for i, _id in enumerate(ids):
                n = self._by_id.get(_id)
                if n and n.get("content"):
                    rows.append(i); arts.append(n)
            mat = mat[rows]
            client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
            self._np = np
            self._vec = (mat, arts, client, meta.get("model", "voyage-3-large"), meta.get("dim", 1024))
        except Exception as e:
            print(f"[RAG] 벡터 초기화 실패 → 키워드 폴백: {e}")
            self._vec = None

    def search(self, query: str, top_k: int = 12) -> list:
        """벡터 검색(가능 시) → 의미 유사 조문. 실패·미설정 시 키워드 FTS 폴백."""
        if self._vec:
            try:
                return self._vector_search(query, top_k)
            except Exception as e:
                print(f"[RAG] 벡터 검색 오류 → 키워드 폴백: {e}")
        return self._keyword_search(query, top_k)

    def _vector_search(self, query: str, top_k: int) -> list:
        mat, arts, client, model, dim = self._vec
        np = self._np
        r = client.embed([query], model=model, input_type="query",
                         output_dimension=dim, truncation=True)
        q = np.asarray(r.embeddings[0], dtype=np.float32)
        n = np.linalg.norm(q)
        if n:
            q = q / n
        scores = mat @ q                       # 코사인(정규화됨) = 내적
        k = min(top_k, len(arts))
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        return [arts[i] for i in idx]

    def _keyword_search(self, query: str, top_k: int = 12) -> list:
        tokens = _tokenize(query)
        if not tokens:
            return []
        scored = []
        for art in self._articles:
            title = art.get("title", "")
            law_nm = art.get("law_nm", "")
            content = art.get("content", "")
            tags = art.get("domain_tags", [])

            title_hay = (title + " " + law_nm).lower()
            content_low = content.lower()

            score = sum(title_hay.count(t) * 3 + content_low.count(t) for t in tokens)
            # 도메인 태그 매칭 가중치
            score += sum(2 for t in tokens if any(t in tag.lower() for tag in tags))

            if score > 0:
                scored.append((score, art))

        scored.sort(key=lambda x: -x[0])
        return [art for _, art in scored[:top_k]]

    def lookup(self, queries: list) -> list:
        """조문명/노드id 목록 → 원문 본문. 외부 앱(arch-law-diagnose 등) 그라운딩용.

        각 query: 노드 id 직접 매칭 → 실패 시 조문명에서 id 구성 후 정확 매칭.
        검색 추정은 하지 않음(틀린 조문 본문 주입은 환각보다 위험).
        graph 미보유 조문은 found=False (호출부에서 degrade).
        """
        out = []
        for q in queries:
            q = (q or "").strip()
            if not q:
                out.append({"query": q, "found": False})
                continue
            node = self._by_id.get(q)  # 이미 정확한 노드 id 인 경우(?node= 딥링크 등)
            if node is None or not node.get("content"):
                cid = _name_to_node_id(q)
                node = self._by_id.get(cid) if cid else None
            if node is None or not node.get("content"):
                out.append({"query": q, "found": False})
                continue
            out.append({
                "query": q,
                "found": True,
                "id": node.get("id"),
                "law_nm": node.get("law_nm"),
                "article_no": node.get("article_no"),
                "title": node.get("title"),
                "content": node.get("content"),
                "source_url": node.get("source_url"),
            })
        return out

    def _fmt(self, art: dict, max_chars: int = 1500) -> str:
        law_nm = art.get("law_nm", "")
        no = art.get("article_no", "")
        title = art.get("title", "")
        content = art.get("content", "")
        if len(content) > max_chars:
            content = content[:max_chars] + "…(이하 생략)"
        label = f"제{no}조" if re.match(r"^\d", no or "") else (no or "")
        return f"[{law_nm} / {label} {title}]\n{content}"

    async def answer_stream(self, question: str, selected_id: str = None):
        """SSE 청크 dict 를 비동기로 yield."""
        context_arts = self.search(question, top_k=12)

        # 현재 Reader에서 열린 조문이 있으면 컨텍스트 맨 앞에 추가
        if selected_id:
            node = self._by_id.get(selected_id)
            if node and node.get("type") == "article":
                if not any(a["id"] == selected_id for a in context_arts):
                    context_arts.insert(0, node)

        source_ids = [a["id"] for a in context_arts]

        if not context_arts:
            yield {"type": "token", "content": "관련 조문을 찾지 못했습니다. 좀 더 구체적인 키워드로 질문해주세요."}
            yield {"type": "done", "source_ids": []}
            return

        context_block = "\n\n---\n\n".join(self._fmt(a) for a in context_arts)
        user_msg = (
            f"## 참조 조문 ({len(context_arts)}개)\n\n"
            f"{context_block}\n\n"
            f"---\n\n"
            f"## 질문\n\n{question}\n\n"
            f"위 조문들에만 근거해서 답변하세요. "
            f"답변에서 특정 조문을 인용할 때는 반드시 법령명과 조문번호를 함께 쓰세요."
        )

        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=2500,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            ) as stream:
                async for text in stream.text_stream:
                    yield {"type": "token", "content": text}
        except Exception as exc:
            yield {"type": "token", "content": f"\n\n[오류] {exc}"}

        yield {"type": "done", "source_ids": source_ids}
