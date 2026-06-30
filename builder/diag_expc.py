"""법령해석례(expc) 가용 건수 진단 스크립트.

현재 EXPC_KEYWORDS 로 검색 가능한 고유 해석례 수 vs EXPC_CAP 비교.
실행: 프로젝트 루트에서
  D:\\APPS\\arch-law-diagnose\\backend\\.venv\\Scripts\\python.exe builder\\diag_expc.py
"""
from __future__ import annotations

import asyncio
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from law_go_kr_client import LawGoKrClient  # noqa: E402

# 현재 build_graph.py 와 동일한 키워드
_CARD_TOPIC_KEYWORDS = [
    "지구단위계획", "기반시설", "재건축", "재개발", "정비사업",
]
EXPC_KEYWORDS = [
    "건축법", "건폐율", "용적률", "건축물 높이", "주차장법", "용도지역", "녹색건축물",
    "이격거리", "대지경계", "용도변경", "건축허가", "건축신고", "위반건축물",
    "가설건축물", "국토계획법", "건축물 대수선", "부설주차장", "조경",
    "일조", "도로 사선",
    *_CARD_TOPIC_KEYWORDS,
]

# 추가 후보 — 실무 상황어
CANDIDATE_KEYWORDS = [
    "대수선 범위", "이행강제금", "가설건축물 존치", "건축허가 취소",
    "일조권 침해", "조경 면제", "장애인 편의시설", "건축선",
    "피난 안전구역", "방화구획", "건폐율 완화", "용적률 완화",
    "건축물 용도 분류", "바닥면적 산정", "연면적 산정",
    "주차장 설치 제외", "공개공지", "다중주택", "다가구주택",
]

EXPC_CAP = 240


async def main() -> None:
    client = LawGoKrClient()

    print("=" * 60)
    print("[1] 현재 키워드로 수집 가능한 해석례 수")
    print("=" * 60)

    idx: dict[str, dict] = {}
    kw_hits: dict[str, int] = {}
    for kw in EXPC_KEYWORDS:
        results = await client.search_expc(kw)
        new = 0
        for it in results:
            if it["expc_id"] not in idx:
                idx[it["expc_id"]] = it
                new += 1
        kw_hits[kw] = new
        print(f"  [{kw}] 신규 {new}건 (누적 {len(idx)}건)")

    print(f"\n  → 현재 키워드 고유 해석례: {len(idx)}건  (CAP={EXPC_CAP})")
    if len(idx) > EXPC_CAP:
        print(f"  ⚠  CAP이 binding — {len(idx) - EXPC_CAP}건 손실")
    else:
        print(f"  ✓  CAP 여유 있음 — 키워드 추가로 늘릴 수 있음")

    print()
    print("=" * 60)
    print("[2] 추가 후보 키워드 신규 기여분")
    print("=" * 60)

    extra_idx: dict[str, dict] = {}
    for kw in CANDIDATE_KEYWORDS:
        results = await client.search_expc(kw)
        new = 0
        for it in results:
            if it["expc_id"] not in idx and it["expc_id"] not in extra_idx:
                extra_idx[it["expc_id"]] = it
                new += 1
        if new:
            print(f"  [{kw}] +{new}건 신규")

    print(f"\n  → 후보 키워드 추가 시 신규 확보: {len(extra_idx)}건")
    print(f"  → 합계 잠재 해석례: {len(idx) + len(extra_idx)}건")

    print()
    print("=" * 60)
    print("[3] 대표 샘플 — 안건명 미리보기 (상위 10건)")
    print("=" * 60)
    for i, it in enumerate(list(idx.values())[:10], 1):
        print(f"  {i:2}. {it['안건명'][:60]}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
