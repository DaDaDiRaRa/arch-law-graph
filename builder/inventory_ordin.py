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

# ─── 전국 군(郡) 목록 — (군명, 상위 도/광역시). 검색·RAG·원문 corpus용. ───
# 군도 기초자치단체라 자체 조례(건축·주차·군계획·녹색) 보유. 단 카드는 도단위 적용(미생성).
# 군의 용도지역 조례는 명칭이 다양: "○○군 도시계획/군계획/계획 조례" → COUNTY_PLAN_CANON 으로 흡수.
# 광역시 산하 군(강화·옹진·달성·군위·울주·기장)은 자체 군계획 조례 없을 수 있음(광역시 도시계획조례 적용).
COUNTIES: list[tuple[str, str]] = [
    # 경기도 (3)
    ("가평군", "경기도"), ("양평군", "경기도"), ("연천군", "경기도"),
    # 강원특별자치도 (11)
    ("홍천군", "강원특별자치도"), ("횡성군", "강원특별자치도"), ("영월군", "강원특별자치도"),
    ("평창군", "강원특별자치도"), ("정선군", "강원특별자치도"), ("철원군", "강원특별자치도"),
    ("화천군", "강원특별자치도"), ("양구군", "강원특별자치도"), ("인제군", "강원특별자치도"),
    ("고성군", "강원특별자치도"), ("양양군", "강원특별자치도"),
    # 충청북도 (8)
    ("보은군", "충청북도"), ("옥천군", "충청북도"), ("영동군", "충청북도"), ("증평군", "충청북도"),
    ("진천군", "충청북도"), ("괴산군", "충청북도"), ("음성군", "충청북도"), ("단양군", "충청북도"),
    # 충청남도 (7)
    ("금산군", "충청남도"), ("부여군", "충청남도"), ("서천군", "충청남도"), ("청양군", "충청남도"),
    ("홍성군", "충청남도"), ("예산군", "충청남도"), ("태안군", "충청남도"),
    # 전북특별자치도 (8)
    ("완주군", "전북특별자치도"), ("진안군", "전북특별자치도"), ("무주군", "전북특별자치도"),
    ("장수군", "전북특별자치도"), ("임실군", "전북특별자치도"), ("순창군", "전북특별자치도"),
    ("고창군", "전북특별자치도"), ("부안군", "전북특별자치도"),
    # 전라남도 (17)
    ("담양군", "전라남도"), ("곡성군", "전라남도"), ("구례군", "전라남도"), ("고흥군", "전라남도"),
    ("보성군", "전라남도"), ("화순군", "전라남도"), ("장흥군", "전라남도"), ("강진군", "전라남도"),
    ("해남군", "전라남도"), ("영암군", "전라남도"), ("무안군", "전라남도"), ("함평군", "전라남도"),
    ("영광군", "전라남도"), ("장성군", "전라남도"), ("완도군", "전라남도"), ("진도군", "전라남도"),
    ("신안군", "전라남도"),
    # 경상북도 (12)
    ("의성군", "경상북도"), ("청송군", "경상북도"), ("영양군", "경상북도"), ("영덕군", "경상북도"),
    ("청도군", "경상북도"), ("고령군", "경상북도"), ("성주군", "경상북도"), ("칠곡군", "경상북도"),
    ("예천군", "경상북도"), ("봉화군", "경상북도"), ("울진군", "경상북도"), ("울릉군", "경상북도"),
    # 경상남도 (10)
    ("의령군", "경상남도"), ("함안군", "경상남도"), ("창녕군", "경상남도"), ("고성군", "경상남도"),
    ("남해군", "경상남도"), ("하동군", "경상남도"), ("산청군", "경상남도"), ("함양군", "경상남도"),
    ("거창군", "경상남도"), ("합천군", "경상남도"),
    # 광역시 산하 군 (6)
    ("기장군", "부산광역시"),
    ("달성군", "대구광역시"), ("군위군", "대구광역시"),
    ("강화군", "인천광역시"), ("옹진군", "인천광역시"),
    ("울주군", "울산광역시"),
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

# ─── 군(郡) 용도지역(건폐율·용적률) 조례 — 명칭 변형 흡수 ───
# 군은 "○○군 도시계획/군계획/계획 조례" 로 제각각 → 접미사 화이트리스트로 채택, 위원회·재정·시설 등 배제.
COUNTY_PLAN_CANON = ["도시계획조례", "도시·군계획조례", "군계획조례", "계획조례"]
COUNTY_PLAN_EXCL = ["시행규칙", "운영", "위원회", "재정", "심의", "시설",
                    "특별회계", "먹거리", "보상", "공장", "기금", "경관", "관리지역"]
COUNTY_PLAN_KW = ["군계획", "도시계획", "계획"]


async def county_plan(http: httpx.AsyncClient, gun: str, org: str) -> dict | None:
    """군 용도지역 조례 1건. 여러 키워드 검색 결과를 합쳐 canon 접미사로 채택."""
    items: list[dict] = []
    seen = set()
    for kw in COUNTY_PLAN_KW:
        for it in await search(http, f"{gun} {kw}"):
            mst = (it.get("자치법규일련번호") or "").strip()
            key = (it.get("자치법규명", ""), mst)
            if key not in seen:
                seen.add(key)
                items.append(it)
    return pick(items, gun, org, ["조례"], COUNTY_PLAN_EXCL, COUNTY_PLAN_CANON)


def org_of(city: str, parent: str | None) -> str:
    """법제처 지자체기관명 형식. 광역/특별자치=시명, 도 산하 시=\"도 시\"."""
    return city if parent is None else f"{parent} {city}"


def clean_name(nm: str) -> str:
    """자치법규명 끝의 개정 꼬리표 제거 — \"○○ 조례 [제명개정 2020. 10. 5.]\" → \"○○ 조례\".

    법제처 검색결과 일부는 자치법규명 끝에 개정표시를 붙임(청도군 군계획 조례 등).
    build_graph 의 search_ordin 도 동일 정규화로 비교해야 MST 를 다시 찾음.
    """
    return re.sub(r"\s*\[[^\]]*\]\s*$", "", nm).strip()


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
        nm = clean_name((it.get("자치법규명") or "").strip())   # 개정 꼬리표 제거 후 비교·저장
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


async def _resolve(http: httpx.AsyncClient, name: str, parent: str | None,
                   county: bool) -> dict:
    """한 지자체의 4조례 해소 → row dict. 군은 도시계획 슬롯에 county_plan 사용."""
    org = org_of(name, parent)
    row: dict = {"city": name, "org": org, "county": county}
    marks = []
    for i, (key, kw, incl, excl, canon) in enumerate(TYPES):
        if county and i == 0:                       # 군 용도지역 = 명칭 변형 흡수
            hit = await county_plan(http, name, org)
        else:
            hit = pick(await search(http, f"{name} {kw}"), name, org, incl, excl, canon)
        row[key] = hit
        marks.append("✓" if hit else "·")
    found_orgs = {h["org"] for h in (row[k] for k, *_ in TYPES) if h}
    org_note = "" if found_orgs in ({org}, set()) else f"  ⚠기관명:{sorted(found_orgs)}"
    print(f"  {' '.join(marks)}  {name:<8} ({org}){org_note}")
    return row


async def main() -> None:
    if not KEY:
        sys.exit("✗ LAW_API_KEY 미설정 (.env 확인)")

    only = sys.argv[1:]
    def keep(n: str) -> bool:
        return not only or any(o in n for o in only)
    city_targets = [(c, p, False) for c, p in CITIES if keep(c)]
    gun_targets = [(c, p, True) for c, p in COUNTIES if keep(c)]

    rows: list[dict] = []
    gun_rows: list[dict] = []
    async with httpx.AsyncClient(timeout=20) as http:
        if city_targets:
            print("── 시(市) ──")
            for name, parent, _ in city_targets:
                rows.append(await _resolve(http, name, parent, False))
        if gun_targets:
            print("── 군(郡) ──")
            for name, parent, _ in gun_targets:
                gun_rows.append(await _resolve(http, name, parent, True))

    # ─── CSV ───
    csv_path = ROOT / "builder" / "inventory_ordin.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["지자체", "구분", "기관명(입력)", "조례종류", "발견조례명", "발견기관명", "MST"])
        for r in rows + gun_rows:
            for key, *_ in TYPES:
                h = r[key]
                w.writerow([r["city"], "군" if r["county"] else "시", r["org"], key,
                            h["name"] if h else "", h["org"] if h else "",
                            h["mst"] if h else ""])

    # ─── build_graph.py 가 import 하는 ORDIN_GROUP 모듈 생성 ───
    # 단일 진실원천(single source of truth): 인벤토리 재실행만으로 전국 목록 갱신.
    grp_path = ROOT / "builder" / "ordin_group.py"
    old_pairs: set[tuple[str, str]] = set()
    if grp_path.exists():
        old_pairs = set(re.findall(r'\("([^"]+)",\s*"([^"]+)"\)', grp_path.read_text(encoding="utf-8")))
    lines = [
        '"""전국 시·군 조례 목록 — builder/inventory_ordin.py 자동 생성.',
        "",
        "수동 편집 금지. 갱신: python builder/inventory_ordin.py 재실행.",
        "시(市)는 카드+검색+RAG, 군(郡)은 검색+RAG+원문(카드는 도단위 적용).",
        '"""',
        "",
        "ORDIN_GROUP = [",
        "    # ── 경기도 도(道) 단위 — 자체 조례 없는 시군 적용(검색·RAG용, 카드 미생성) ──",
        '    ("경기도", "경기도 도시계획 조례"),',
        '    ("경기도", "경기도 건축 조례"),',
    ]
    def emit(rs: list[dict], header: str) -> None:
        lines.append(f"    # ════════ {header} ════════")
        for r in rs:
            got = [k for k, *_ in TYPES if r[k]]
            if not got:
                continue
            lines.append(f"    # ── {r['city']} ({len(got)}/4) ──")
            for key, *_ in TYPES:
                h = r[key]
                if h:
                    lines.append(f'    ("{h["org"]}", "{h["name"]}"),')
    emit(rows, "시(市)")
    emit(gun_rows, "군(郡) — 검색·RAG·원문 corpus")
    lines.append("]")
    grp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ─── 이전 목록과 diff — 지자체기관명 개편·조례 폐지/개칭이 조용히 묻히지 않도록 명시 ───
    # (Stage E-11에서 광주·전남 기관명 개편, 제주 조례 개칭이 재시도로도 복구 안 되는 채로
    #  ordin_group.py 에 그대로 남아있다가 조례 73건 fetch 실패로 뒤늦게 발견된 사고 재발 방지)
    new_pairs = set(re.findall(r'\("([^"]+)",\s*"([^"]+)"\)', "\n".join(lines)))
    removed, added = old_pairs - new_pairs, new_pairs - old_pairs
    if old_pairs and (removed or added):
        print(f"\n⚠ ordin_group.py 변경 감지 — 제거 {len(removed)}건, 추가 {len(added)}건 "
              "(지자체기관명 개편·조례 폐지/개칭 가능성 — 확인 후 커밋):")
        for org, name in sorted(removed):
            print(f"    - {org} | {name}")
        for org, name in sorted(added):
            print(f"    + {org} | {name}")

    # ─── 요약 ───
    def stat(rs):
        full = sum(1 for r in rs if all(r[k] for k, *_ in TYPES))
        core3 = sum(1 for r in rs if all(r[k] for k in ("도시계획", "건축", "주차")))
        none = sum(1 for r in rs if not any(r[k] for k, *_ in TYPES))
        return full, core3, none
    if rows:
        f, c, n = stat(rows)
        print(f"\n── 시 {len(rows)}개 ── 4종완비:{f} 핵심3종:{c} 0종:{n}")
    if gun_rows:
        f, c, n = stat(gun_rows)
        print(f"── 군 {len(gun_rows)}개 ── 4종완비:{f} 핵심3종:{c} 0종:{n}")
    print(f"  CSV: {csv_path}")
    print(f"  ORDIN_GROUP: {grp_path}")


if __name__ == "__main__":
    asyncio.run(main())
