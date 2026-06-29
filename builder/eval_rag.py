"""
builder/eval_rag.py  —  RAG 품질 평가 하네스

용법:
  python builder/eval_rag.py              # 전체 35문항
  python builder/eval_rag.py --limit 10   # 앞 10문항만 (빠른 점검)
  python builder/eval_rag.py --out results/baseline.json

산출물:
  - 콘솔 요약 테이블 (결론 일치율 / 법령 인용률 / 카테고리별)
  - JSON 상세 결과 (--out 지정 시 파일 저장)

의존:
  - ANTHROPIC_API_KEY  — judge (claude-opus-4-8) + RAG 답변 생성
  - VOYAGE_API_KEY     — (선택) 없으면 키워드 FTS 폴백
  - backend/rag_engine.py + data/graph.json (프로젝트 루트 기준)

설계 원칙:
  - RAG 답변 생성: 프로덕션과 동일 모델(ANTHROPIC_MODEL env, 기본 claude-sonnet-4-6)
  - Judge:         claude-opus-4-8 고정 (tool_choice 강제 → 구조화 출력)
  - 문항 35개: factual(수치 정답 명확) + interpretive(서술형)
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# 프로젝트 루트 .env 로드 (VOYAGE_API_KEY, ANTHROPIC_API_KEY 등)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from anthropic import AsyncAnthropic
from backend.rag_engine import RAGEngine

# ── 벤치마크 문항 ─────────────────────────────────────────────────────────────
# ground_truth: judge가 RAG 답변과 비교할 정답 키워드/내용.
# 모두 web/src/zoning.js·parking.js 손큐레이션 수치에서 파생.

BENCH_SET = [
    # ── 건폐율·용적률 — 국가 기준 ────────────────────────────────────────────
    {
        "id": "bcr_nat_1",
        "category": "factual",
        "question": "국토계획법 시행령상 제2종전용주거지역 건폐율 국가 상한은?",
        "ground_truth": "50%",
    },
    {
        "id": "far_nat_1",
        "category": "factual",
        "question": "국토계획법 시행령상 중심상업지역 용적률 국가 상한은?",
        "ground_truth": "1500%",
    },
    {
        "id": "bcr_nat_2",
        "category": "factual",
        "question": "자연녹지지역 건폐율 국가 상한과 그 근거 법조문은?",
        "ground_truth": "건폐율 20%, 국토의 계획 및 이용에 관한 법률 시행령 제84조",
    },
    {
        "id": "bcr_nat_3",
        "category": "factual",
        "question": "계획관리지역 건폐율 국가 기준은?",
        "ground_truth": "40%",
    },
    {
        "id": "far_nat_2",
        "category": "factual",
        "question": "준공업지역 용적률 국가 상한은?",
        "ground_truth": "400%",
    },
    {
        "id": "far_nat_3",
        "category": "factual",
        "question": "일반공업지역 용적률 국가 상한과 전용공업지역의 차이는?",
        "ground_truth": "일반공업 350%, 전용공업 300%",
    },
    # ── 건폐율·용적률 — 서울 조례 ────────────────────────────────────────────
    {
        "id": "bcr_far_seoul_1",
        "category": "factual",
        "question": "서울특별시 도시계획 조례상 제2종일반주거지역 건폐율과 용적률은?",
        "ground_truth": "건폐율 60%, 용적률 200%",
    },
    {
        "id": "bcr_far_seoul_2",
        "category": "factual",
        "question": "서울 중심상업지역 건폐율은 국가 상한(90%)과 비교해 얼마인가?",
        "ground_truth": "서울 60%(국가 90%보다 낮음, 조례로 강화)",
    },
    {
        "id": "bcr_far_seoul_3",
        "category": "factual",
        "question": "서울 준공업지역 용적률은?",
        "ground_truth": "400%",
    },
    {
        "id": "bcr_far_seoul_4",
        "category": "factual",
        "question": "서울 보전녹지지역 용적률은?",
        "ground_truth": "50%",
    },
    # ── 건폐율·용적률 — 부산 조례 ────────────────────────────────────────────
    {
        "id": "bcr_far_busan_1",
        "category": "factual",
        "question": "부산광역시 중심상업지역 건폐율은?",
        "ground_truth": "80%",
    },
    {
        "id": "bcr_far_busan_2",
        "category": "factual",
        "question": "부산 제2종일반주거지역 용적률과 서울 동일 용도지역 용적률 차이는?",
        "ground_truth": "부산 220%(단 대지 1,000㎡ 초과 시 200%), 서울 200%. 부산이 더 높음.",
    },
    # ── 일조권 ────────────────────────────────────────────────────────────────
    {
        "id": "sunlight_1",
        "category": "factual",
        "question": "건축법령상 정북방향 인접대지경계선 기준 일조 이격 규정은?",
        "ground_truth": "높이 10m 이하: 1.5m 이상 이격, 높이 10m 초과: 해당 건축물 높이의 1/2 이상 이격",
    },
    {
        "id": "sunlight_2",
        "category": "factual",
        "question": "정북방향 일조 이격 기준의 근거 법조문은?",
        "ground_truth": "건축법 제61조, 건축법 시행령 제86조",
    },
    {
        "id": "sunlight_3",
        "category": "interpretive",
        "question": "어떤 용도지역에서 정북 일조권 사선제한이 적용되는가?",
        "ground_truth": "주거지역(전용주거·일반주거)에 적용. 준주거·상업·공업·녹지지역은 미적용. 건축법 제61조·시행령 제86조 근거.",
    },
    # ── 부설주차장 ────────────────────────────────────────────────────────────
    {
        "id": "pk_nat_1",
        "category": "factual",
        "question": "주차장법 시행령 별표1 국가 기준으로 위락시설 부설주차장 설치 기준은?",
        "ground_truth": "시설면적 100㎡당 1대",
    },
    {
        "id": "pk_nat_2",
        "category": "factual",
        "question": "국가 기준 창고시설 부설주차장 기준은?",
        "ground_truth": "시설면적 400㎡당 1대",
    },
    {
        "id": "pk_seoul_1",
        "category": "factual",
        "question": "서울시 위락시설 부설주차장 기준은? 국가 기준과 비교해서.",
        "ground_truth": "서울 67㎡당 1대(국가 100㎡당 1대보다 강화)",
    },
    {
        "id": "pk_seoul_2",
        "category": "factual",
        "question": "서울시 제1·2종 근린생활시설 부설주차장 기준은?",
        "ground_truth": "시설면적 134㎡당 1대",
    },
    {
        "id": "pk_busan_1",
        "category": "factual",
        "question": "부산 단독주택 주차 기준의 국가 기준과 다른 특이사항은?",
        "ground_truth": "부산은 기준면적 180㎡(국가 150㎡), 가산면적 120㎡(국가 100㎡). 부산이 더 완화.",
    },
    # ── 법령 근거·체계 ────────────────────────────────────────────────────────
    {
        "id": "law_1",
        "category": "interpretive",
        "question": "건폐율과 용적률을 규정하는 상위법 조문은 각각 무엇인가?",
        "ground_truth": "건폐율: 국토의 계획 및 이용에 관한 법률 제77조·시행령 제84조, 용적률: 동법 제78조·시행령 제85조",
    },
    {
        "id": "law_2",
        "category": "interpretive",
        "question": "지자체 조례가 국가 법령보다 엄격한 건폐율을 적용할 수 있나? 법적 근거와 사례는?",
        "ground_truth": "가능. 국토계획법 제77조에서 국가 상한 이하 범위에서 조례로 정함. 예: 서울 중심상업지역 건폐율 60%(국가 상한 90%).",
    },
    {
        "id": "law_3",
        "category": "interpretive",
        "question": "부설주차장 설치 의무의 법적 근거와 지자체 조례의 역할은?",
        "ground_truth": "주차장법 제19조·시행령 제6조·별표1이 국가 기준. 지자체는 조례로 강화 또는 완화 가능.",
    },
    # ── 완화·인센티브 ─────────────────────────────────────────────────────────
    {
        "id": "incentive_1",
        "category": "interpretive",
        "question": "녹색건축 인증을 받으면 용적률을 얼마나 완화받을 수 있나? 근거 기준은?",
        "ground_truth": "녹색건축 최우수 6%, 우수 3% 완화. 건축물의 에너지절약설계기준(국토부 고시) 별표9 기준.",
    },
    {
        "id": "incentive_2",
        "category": "interpretive",
        "question": "공개공지를 설치하면 용적률 완화를 받을 수 있나? 관련 법조문은?",
        "ground_truth": "건축법 제43조·시행령 제27조의2에 따라 공개공지 설치 시 용적률·건폐율 완화. 지자체 조례로 구체적 완화율 결정.",
    },
    {
        "id": "incentive_3",
        "category": "interpretive",
        "question": "ZEB(제로에너지건축물) 인증 등급별 용적률 완화 범위는?",
        "ground_truth": "ZEB 1등급 15%~5등급 11% 완화. 에너지절약설계기준 별표9 기준.",
    },
    # ── 대지 안의 공지(이격) ─────────────────────────────────────────────────
    {
        "id": "setback_1",
        "category": "interpretive",
        "question": "대지 안의 공지(건축선·인접대지경계선 이격) 규정의 법적 근거는?",
        "ground_truth": "건축법 제58조, 건축법 시행령 제80조의2. 건축물 외벽에서 대지경계선까지 이격 의무.",
    },
    # ── 조경 ──────────────────────────────────────────────────────────────────
    {
        "id": "landscape_1",
        "category": "interpretive",
        "question": "건축물 조경 설치 의무 기준의 법적 근거는?",
        "ground_truth": "건축법 제42조, 건축법 시행령 제27조. 연면적·대지면적 기준으로 의무 조경면적 산정.",
    },
    # ── 건축위원회 심의 ───────────────────────────────────────────────────────
    {
        "id": "review_1",
        "category": "interpretive",
        "question": "건축법상 건축위원회 법정 심의 대상 건축물 기준은?",
        "ground_truth": "건축법 시행령 제5조의5①: 연면적 10만㎡ 이상 등 대규모·특수구조 건축물이 법정 심의 대상.",
    },
    # ── 복합 질의 ─────────────────────────────────────────────────────────────
    {
        "id": "complex_1",
        "category": "interpretive",
        "question": "서울 제2종일반주거지역에 공동주택을 지을 때 건폐율·용적률·일조권·주차를 종합해서 설명해줘.",
        "ground_truth": "건폐율 60%, 용적률 200%(서울 조례), 정북 일조 적용(10m↓ 1.5m / 초과 1/2), 세대당 주차 1대 이상(전용면적 규모별 차등).",
    },
    {
        "id": "complex_2",
        "category": "interpretive",
        "question": "서울 근린상업지역과 일반상업지역의 건폐율·용적률 차이와 근거 조문은?",
        "ground_truth": "근린상업: BCR 60%/FAR 600%, 일반상업: BCR 60%/FAR 800%. 서울특별시 도시계획 조례 제44조·제48조.",
    },
    {
        "id": "complex_3",
        "category": "interpretive",
        "question": "부산과 서울의 제1종일반주거지역 건폐율·용적률을 비교해줘.",
        "ground_truth": "서울 BCR 60%/FAR 150%, 부산 BCR 60%/FAR 180%. 각 도시 도시계획 조례가 국가 상한(BCR 60%/FAR 200%) 범위 내에서 다르게 설정.",
    },
    {
        "id": "complex_4",
        "category": "interpretive",
        "question": "서울·부산·국가 기준에서 위락시설 부설주차장 기준 비교는?",
        "ground_truth": "국가 100㎡당 1대, 서울 67㎡당 1대(강화), 부산 67㎡당 1대(강화). 서울·부산이 동일하게 국가보다 강화.",
    },
    {
        "id": "complex_5",
        "category": "interpretive",
        "question": "건축물 높이 제한과 관련해 일조권 사선제한과 도로사선제한의 차이를 설명해줘.",
        "ground_truth": "일조권 사선: 정북방향 기준, 주거지역만 적용, 건축법 제61조·시행령 제86조. 도로사선: 건축선에서 도로 너비 기준으로 경사각 제한, 건축법 제60조. 적용 기준·방향이 다름.",
    },
]

# ── Judge 설정 ───────────────────────────────────────────────────────────────

_JUDGE_TOOLS = [
    {
        "name": "submit_evaluation",
        "description": "RAG 답변 평가 결과를 제출합니다",
        "input_schema": {
            "type": "object",
            "properties": {
                "conclusion_match": {
                    "type": "boolean",
                    "description": "RAG 답변의 핵심 결론이 ground_truth와 일치하는가 (수치·조건 포함, 부분 정답은 false)",
                },
                "law_search_ok": {
                    "type": "boolean",
                    "description": "관련 법령명과 조문번호를 하나 이상 올바르게 찾아 인용했는가",
                },
                "reason": {
                    "type": "string",
                    "description": "평가 근거 1~2줄 요약",
                },
            },
            "required": ["conclusion_match", "law_search_ok", "reason"],
        },
    }
]

_JUDGE_SYSTEM = """당신은 건축법규 RAG 시스템의 답변을 평가하는 엄격한 judge입니다.
질문, 정답(ground_truth), RAG 답변을 비교해 공정하게 평가하세요.

평가 기준:
- conclusion_match: 핵심 수치·조건이 ground_truth와 일치하면 true. 부분 정답·누락은 false.
- law_search_ok: 정확한 법령명과 조문번호를 하나 이상 올바르게 인용했으면 true.
- interpretive 문항은 핵심 방향이 맞으면 true, 결정적 내용 누락은 false.

반드시 submit_evaluation 도구를 호출해 결과를 제출하세요."""


async def _judge(client: AsyncAnthropic, item: dict, rag_answer: str) -> dict:
    """claude-opus-4-8로 단일 문항 채점. dict 반환."""
    user_msg = (
        f"## 질문\n{item['question']}\n\n"
        f"## 정답 (ground_truth)\n{item['ground_truth']}\n\n"
        f"## RAG 답변\n{rag_answer}\n\n"
        "위 RAG 답변을 평가하고 submit_evaluation을 호출하세요."
    )
    resp = await client.messages.create(
        model="claude-opus-4-8",
        max_tokens=512,
        system=_JUDGE_SYSTEM,
        tools=_JUDGE_TOOLS,
        tool_choice={"type": "tool", "name": "submit_evaluation"},
        messages=[{"role": "user", "content": user_msg}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "submit_evaluation":
            return block.input
    return {"conclusion_match": False, "law_search_ok": False, "reason": "judge 파싱 실패"}


async def _rag_answer(engine: RAGEngine, question: str) -> tuple[str, list]:
    """RAG 스트리밍을 모아 (full_text, source_ids) 반환."""
    parts, source_ids = [], []
    async for chunk in engine.answer_stream(question):
        if chunk["type"] == "token":
            parts.append(chunk["content"])
        elif chunk["type"] == "done":
            source_ids = chunk.get("source_ids", [])
    return "".join(parts), source_ids


# ── 메인 ─────────────────────────────────────────────────────────────────────

async def run_eval(limit: int | None = None, out_path: str | None = None):
    print("[eval] RAGEngine 초기화…")
    engine = RAGEngine()
    judge_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    bench = BENCH_SET[:limit] if limit else BENCH_SET
    results = []
    rag_model = os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-6')
    print(f"[eval] {len(bench)}문항 시작 / RAG: {rag_model} / judge: claude-opus-4-8\n")

    t0 = time.time()
    for i, item in enumerate(bench, 1):
        print(f"  [{i:02d}/{len(bench)}] {item['id']:<22}", end=" ", flush=True)
        t1 = time.time()

        answer, source_ids = await _rag_answer(engine, item["question"])
        verdict = await _judge(judge_client, item, answer)

        elapsed = time.time() - t1
        cm = verdict.get("conclusion_match", False)
        lk = verdict.get("law_search_ok", False)
        print(f"결론{'O' if cm else 'X'} 법령{'O' if lk else 'X'}  ({elapsed:.1f}s)  {verdict.get('reason','')[:60]}")

        results.append({
            **item,
            "rag_answer": answer,
            "source_ids": source_ids,
            "verdict": verdict,
            "elapsed_s": round(elapsed, 2),
        })

    total = time.time() - t0
    n = len(results)
    fac = [r for r in results if r["category"] == "factual"]
    itp = [r for r in results if r["category"] == "interpretive"]

    def pct(lst, key):
        return sum(1 for r in lst if r["verdict"].get(key)) / max(len(lst), 1) * 100

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 결론 일치율  {pct(results,'conclusion_match'):5.1f}%   factual {pct(fac,'conclusion_match'):5.1f}%  /  interpretive {pct(itp,'conclusion_match'):5.1f}%
 법령 인용률  {pct(results,'law_search_ok'):5.1f}%   factual {pct(fac,'law_search_ok'):5.1f}%  /  interpretive {pct(itp,'law_search_ok'):5.1f}%
 총 문항      {n}  (factual {len(fac)} / interpretive {len(itp)})
 소요 시간    {total:.1f}s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")

    # 실패 문항 목록
    failures = [r for r in results if not r["verdict"].get("conclusion_match")]
    if failures:
        print(f"\n결론 불일치 {len(failures)}건:")
        for r in failures:
            print(f"  [{r['id']}] {r['verdict'].get('reason','')[:80]}")

    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[eval] 결과 저장 → {out_path}")

    return results


def main():
    import argparse
    ap = argparse.ArgumentParser(description="arch-law-graph RAG 평가 하네스")
    ap.add_argument("--limit", type=int, default=None, help="평가할 최대 문항 수")
    ap.add_argument("--out", type=str, default=None, help="결과 저장 JSON 경로")
    args = ap.parse_args()
    asyncio.run(run_eval(args.limit, args.out))


if __name__ == "__main__":
    main()
