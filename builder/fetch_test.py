"""건축법 1개 법령 fetch 동작 검증 — Phase 1 최소 확인용.

실행: 프로젝트 루트(D:\\APPS\\arch-law-graph)에서
  <자매앱 venv>\\python.exe builder\\fetch_test.py
.env 의 LAW_API_KEY 를 사용한다.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Windows 콘솔(cp949)에서도 한글·기호 출력되도록
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from law_go_kr_client import LawGoKrClient  # noqa: E402


async def main() -> None:
    client = LawGoKrClient()

    print("[1] 법령 검색: '건축법'")
    laws = await client.search_law("건축법", law_type="LAW")
    if not laws:
        print("  ✗ 검색 결과 없음 — LAW_API_KEY 또는 네트워크 확인")
        await client.close()
        return
    for law in laws[:5]:
        print(f"  - {law['law_nm']} (MST={law['law_id']}, 시행={law['ef_yd']})")

    # 정확히 '건축법' 인 항목 우선 선택
    target = next((law for law in laws if law["law_nm"] == "건축법"), laws[0])
    print(f"\n[2] 조문 본문 조회: {target['law_nm']} (MST={target['law_id']})")
    articles = await client.get_law_articles(target["law_id"], "LAW")
    print(f"  조문 수: {len(articles)}")
    for a in articles[:5]:
        print(f"  - {a['article_no']} {a['title']}")

    has_ilcho = any("일조" in a.get("title", "") for a in articles)
    print(f"\n  '일조' 관련 조문 포함: {has_ilcho}")
    print(f"\n결과: {'✓ fetch 동작 확인' if articles else '✗ 조문 0건'}")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
