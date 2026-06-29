"""전국 시(市) 조례 인벤토리 — 자동 발견 스크립트.

법제처 ordin API를 도시별로 돌며 4종 핵심 조례(도시계획·건축·주차·녹색건축)의
정확한 자치법규명·지자체기관명·MST를 자동 해소한다. 수동 추측·시행착오 제거용.

출력:
  1) 콘솔 커버리지 표 (도시 × 4조례, ✓/✗)
  2) builder/inventory_ordin.csv  — 전체 매칭 결과
  3) builder/inventory_ordin_group.txt — ORDIN_GROUP 에 바로 붙여넣을 줄

실행 (루트에서):
  D:\\APPS\\arch-law-diagnose\\backend\\.venv\\Scripts\\python.exe builder/inventory_ordin.py
  # 일부만:  ... builder/inventory_ordin.py 포항 김해 춘천
"""
from __future__ import annotations

import asyncio
import csv
import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BASE = "https://www.law.go.kr/DRF"
KEY = os.getenv("LAW_API_KEY", "")

# ─── 전국 시(市) 목록 — (시명, 상위 광역). 광역시·특별자치는 상위=None(기관명=시명 자체) ───
# 카드는 시(市) 단위. 군(郡)·자치구는 제외(상위 도/광역시 기준 적용).
CITIES: list[tuple[str, str | None]] = [
    # 특·광역시·특별자치 (기관명 = 시명 그대로)
    ("서울특별시", None), ("부산광역시", None), ("인천광역시", None),
    ("대구광역시", None), ("대전광역시", None), ("광주광역시", None),
    ("울산광역시", None), ("세종특별자치시", None), ("제주특별자치도", None),
    # 경기도 (28시)
    ("수원시", "경기도"), ("용인시", "경기도"), ("고양시", "경기도"),
    ("성남시", "경기도"), ("부천시", "경기도"), ("화성시", "경기도"),
    ("안산시", "경기도"), ("남양주시", "경기도"), ("안양시", "경기도"),
    ("평택시", "경기도"), ("시흥시", "경기도"), ("파주시", "경기도"),
    ("김포시", "경기도"), ("의정부시", "경기도"), ("광명시", "경기도"),
    ("군포시", "경기도"), ("하남시", "경기도"), ("오산시", "경기도"),
    ("양주시", "경기도"), ("이천시", "경기도"), ("구리시", "경기도"),
    ("안성시", "경기도"), ("포천시", "경기도"), ("의왕시", "경기도"),
    ("여주시", "경기도"), ("동두천시", "경기도"), ("과천시", "경기도"),
    ("광주시", "경기도"),
    # 강원특별자치도 (7시)
    ("춘천시", "강원특별자치도"), ("원주시", "강원특별자치도"), ("강릉시", "강원특별자치도"),
    ("동해시", "강원특별자치도"), ("태백시", "강원특별자치도"), ("속초시", "강원특별자치도"),
    ("삼척시", "강원특별자치도"),
    # 충청북도 (3시)
    ("청주시", "충청북도"), ("충주시", "충청북도"), ("제천시", "충청북도"),
    # 충청남도 (8시)
    ("천안시", "충청남도"), ("공주시", "충청남도"), ("보령시", "충청남도"),
    ("아산시", "충청남도"), ("서산시", "충청남도"), ("논산시", "충청남도"),
    ("계룡시", "충청남도"), ("당진시", "충청남도"),
    # 전북특별자치도 (6시)
    ("전주시", "전북특별자치도"), ("군산시", "전북특별자치도"), ("익산시", "전북특별자치도"),
    ("정읍시", "전북특별자치도"), ("남원시", "전북특별자치도"), ("김제시", "전북특별자치도"),
    # 전라남도 (5시)
    ("목포시", "전라남도"), ("여수시", "전라남도"), ("순천시", "전라남도"),
    ("나주시", "전라남도"), ("광양시", "전라남도"),
    # 경상북도 (10시)
    ("포항시", "경상북도"), ("경주시", "경상북도"), ("김천시", "경상북도"),
    ("안동시", "경상북도"), ("구미시", "경상북도"), ("영주시", "경상북도"),
    ("영천시", "경상북도"), ("상주시", "경상북도"), ("문경시", "경상북도"),
    ("경산시", "경상북도"),
    # 경상남도 (8시)
    ("창원시", "경상남도"), ("진주시", "경상남도"), ("통영시", "경상남도"),
    ("사천시", "경상남도"), ("김해시", "경상남도"), ("밀양시", "경상남도"),
    ("거제시", "경상남도"), ("양산시", "경상남도"),
]

# ─── 조례 4종: (키, 검색키워드, 명칭포함어, 명칭제외어, 표준접미사|None) ───
# 표준접미사가 있으면 자치법규명(공백제거)이 그 중 하나로 끝나야 채택 — 부속·지원 조례 배제.
PARK_CANON = [
    "주차장설치및관리조례", "주차장설치및관리에관한조례",
    "주차장설치및관리운영에관한조례", "주차장설치조례",
    "주차장설치ㆍ관리조례", "주차장조례",
]
TYPES = [
    ("도시계획", "도시계획", ["도시계획", "조례"], ["시행규칙", "운영"], None),
    ("건축",     "건축",     ["건축", "조례"],     ["시행규칙", "위원회", "경관", "녹색", "물 관리", "물관리", "주차", "미관"], None),
    ("주차",     "주차장",   ["주차장", "조례"],   ["시행규칙", "특별회계", "보훈"], PARK_CANON),
    ("녹색",     "녹색건축물", ["녹색건축물", "조례"], ["시행규칙"], None),
]


def org_of(city: str, parent: str | None) -> str:
    """법제처 지자체기관명 형식. 광역/특별자치=시명, 도 산하 시=\"도 시\"."""
    return city if parent is None else f"{parent} {city}"


async def search(http: httpx.AsyncClient, query: str) -> list[dict]:
    """ordin 검색 — 최대 3페이지(display 100)."""
    out: list[dict] = []
    for page in (1, 2, 3):
        params = {"OC": KEY, "target": "ordin", "type": "JSON",
                  "query": query, "display": 100, "page": page}
        try:
            r = await http.get(f"{BASE}/lawSearch.do", params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            print(f"  검색 오류 ({query} p{page}): {e}", file=sys.stderr)
            break
        items = body.get("OrdinSearch", {}).get("law", []) or []
        if isinstance(items, dict):
            items = [items]
        if not items:
            break
        out.extend(items)
    return out


def pick(items: list[dict], city: str, org: str,
         incl: list[str], excl: list[str],
         canon: list[str] | None = None) -> dict | None:
    """후보 중 city·기관명·명칭 규칙에 맞는 최적 1건. 정확명(\"○○시 ○○ 조례\") 우선.

    canon 이 주어지면 자치법규명(공백제거)이 그 접미사 중 하나로 끝나야 채택.
    """
    cands = []
    for it in items:
        nm = (it.get("자치법규명") or "").strip()
        oo = (it.get("지자체기관명") or "").strip()
        if city not in oo:                       # 다른 지자체
            continue
        nm_ns = nm.replace(" ", "")
        if any(w.replace(" ", "") not in nm_ns for w in incl):
            continue
        if any(w.replace(" ", "") in nm_ns for w in excl):
            continue
        if canon and not any(nm_ns.endswith(c.replace(" ", "")) for c in canon):
            continue
        mst = (it.get("자치법규일련번호") or "").strip()
        if not mst:
            m = re.search(r"MST=(\d+)", it.get("자치법규상세링크", ""))
            mst = m.group(1) if m else ""
        if not mst:
            continue
        cands.append({"name": nm, "org": oo, "mst": mst, "len": len(nm)})
    if not cands:
        return None
    # 기관명 정확 일치 + 명칭 짧은(=기본 조례, 개정·부속 아님) 것 우선
    cands.sort(key=lambda c: (c["org"] != org, c["len"]))
    return cands[0]


async def main() -> None:
    if not KEY:
        sys.exit("✗ LAW_API_KEY 미설정 (.env 확인)")

    only = sys.argv[1:]
    targets = [(c, p) for c, p in CITIES
               if not only or any(o in c for o in only)]

    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=20) as http:
        for city, parent in targets:
            org = org_of(city, parent)
            row: dict = {"city": city, "org": org}
            marks = []
            for key, kw, incl, excl, canon in TYPES:
                items = await search(http, f"{city} {kw}")
                hit = pick(items, city, org, incl, excl, canon)
                row[key] = hit
                marks.append("✓" if hit else "·")
            rows.append(row)
            found_orgs = {h["org"] for h in (row[k] for k, *_ in TYPES) if h}
            org_note = "" if found_orgs == {org} or not found_orgs else \
                f"  ⚠기관명:{sorted(found_orgs)}"
            print(f"  {' '.join(marks)}  {city:<8} ({org}){org_note}")

    # ─── CSV ───
    csv_path = ROOT / "builder" / "inventory_ordin.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["시", "기관명(입력)", "조례종류", "발견조례명", "발견기관명", "MST"])
        for r in rows:
            for key, *_ in TYPES:
                h = r[key]
                w.writerow([r["city"], r["org"], key,
                            h["name"] if h else "", h["org"] if h else "",
                            h["mst"] if h else ""])

    # ─── build_graph.py 가 import 하는 ORDIN_GROUP 모듈 생성 ───
    # 단일 진실원천(single source of truth): 인벤토리 재실행만으로 전국 목록 갱신.
    grp_path = ROOT / "builder" / "ordin_group.py"
    lines = [
        '"""전국 시(市) 조례 목록 — builder/inventory_ordin.py 자동 생성.',
        "",
        "수동 편집 금지. 갱신: python builder/inventory_ordin.py 재실행.",
        '"""',
        "",
        "ORDIN_GROUP = [",
        "    # ── 경기도 도(道) 단위 — 자체 조례 없는 시군 적용(검색·RAG용, 카드 미생성) ──",
        '    ("경기도", "경기도 도시계획 조례"),',
        '    ("경기도", "경기도 건축 조례"),',
    ]
    for r in rows:
        got = [k for k, *_ in TYPES if r[k]]
        if not got:
            continue
        lines.append(f"    # ── {r['city']} ({len(got)}/4) ──")
        for key, *_ in TYPES:
            h = r[key]
            if h:
                lines.append(f'    ("{h["org"]}", "{h["name"]}"),')
    lines.append("]")
    grp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ─── 요약 ───
    full = sum(1 for r in rows if all(r[k] for k, *_ in TYPES))
    core3 = sum(1 for r in rows if all(r[k] for k in ("도시계획", "건축", "주차")))
    none = sum(1 for r in rows if not any(r[k] for k, *_ in TYPES))
    print(f"\n── 전국 {len(rows)}개 시 ──")
    print(f"  4종 완비: {full}   핵심3종(도계·건축·주차): {core3}   0종(조례없음): {none}")
    print(f"  CSV: {csv_path}")
    print(f"  ORDIN_GROUP: {grp_path}")


if __name__ == "__main__":
    asyncio.run(main())
