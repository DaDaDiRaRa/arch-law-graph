"""용도지역 카드(건폐율·용적률) 자동추출 + 손큐레이션 대조 검증.

graph.json 의 도시계획 조례 '건폐율'·'용적률' 조문(번호목록 본문)을 파싱해
도시별 zones{key:{bcr,far}} 를 생성하고, web/src/zoning.js 의 기존 REGIONS 와 대조.

실행:
  python builder/extract_zoning.py            # 전국(graph 내 모든 도시계획 조례)
  python builder/extract_zoning.py 서울 부산   # 일부 도시만 + zoning.js 대조
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "data" / "graph.json"
ZONING_JS = ROOT / "web" / "src" / "zoning.js"

# 용도지역명 → zoning.js key
NAME2KEY = {
    "제1종전용주거지역": "1jeon", "제2종전용주거지역": "2jeon",
    "제1종일반주거지역": "1il", "제2종일반주거지역": "2il", "제3종일반주거지역": "3il",
    "준주거지역": "junju", "중심상업지역": "jungsang", "일반상업지역": "ilsang",
    "근린상업지역": "geunsang", "유통상업지역": "yutong",
    "전용공업지역": "jeongong", "일반공업지역": "ilgong", "준공업지역": "jungong",
    "보전녹지지역": "bojnok", "생산녹지지역": "saengnok", "자연녹지지역": "janok",
    "보전관리지역": "bojgwan", "생산관리지역": "saenggwan", "계획관리지역": "gyehoek",
    "농림지역": "nongrim", "자연환경보전지역": "jayeon",
}


def kor_pct(s: str) -> int | None:
    """'50퍼센트'·'1천퍼센트'·'1천300퍼센트'·'1,300%'·'100분의40' → int.

    '100분의 N' 분수표기(= N%)와 '천' 단위 모두 지원. 전부 조례 원문 표기 그대로.
    """
    s = s.replace(",", "").replace(" ", "")
    m = re.search(r"100분의(\d+)", s)        # '100분의 40' = 40%
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)천(\d+)?", s)        # '1천300' = 1300
    if m:
        return int(m.group(1)) * 1000 + (int(m.group(2)) if m.group(2) else 0)
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def parse_ratio_article(content: str) -> dict[str, int]:
    """'N. 용도지역명: 값' 목록 → {key: pct}. 첫 매칭값만(본문 우선).

    공백 제거 후 매칭(이름 내 공백·줄바꿈 무시) + '100분의 N'·'N퍼센트'·'N%' 표기 모두 지원.
    모두 조례 본문 수치 그대로 — 추정·해석 없음.
    """
    out: dict[str, int] = {}
    c = re.sub(r"\s+", "", content)          # 공백·줄바꿈 제거 → '제1종 전용주거지역' = '제1종전용주거지역'
    # 값 토큰: '100분의N' | 'N천M(퍼센트|%)' | 'N(퍼센트|%)'
    val = r"(100분의\d+|\d[\d,]*천?\d*\s*(?:퍼센트|%))"
    for nm, key in NAME2KEY.items():
        m = re.search(re.escape(nm) + r"[^0-9백천분%]{0,6}" + val, c)
        if m:
            v = kor_pct(m.group(1))
            if v is not None:
                out[key] = v
    return out


def load_graph_cities() -> dict[str, dict]:
    """도시계획 조례별로 건폐율·용적률 조문 본문 수집. {조례명: {bcr_art, far_art, bcr{}, far{}}}."""
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    nodes = g["nodes"]
    cities: dict[str, dict] = {}
    for n in nodes:
        law = n.get("law_nm", "")
        if "도시계획 조례" not in law and "도시계획조례" not in law:
            continue
        title = n.get("title", "")
        content = n.get("content", "")
        art = n.get("article_no", "")
        rec = cities.setdefault(law, {})
        if "건폐율" in title:
            parsed = parse_ratio_article(content)
            if parsed and len(parsed) >= len(rec.get("bcr", {})):
                rec["bcr"], rec["bcr_art"], rec["bcr_id"] = parsed, art, n.get("id", "")
        if "용적률" in title:
            parsed = parse_ratio_article(content)
            if parsed and len(parsed) >= len(rec.get("far", {})):
                rec["far"], rec["far_art"], rec["far_id"] = parsed, art, n.get("id", "")
    return cities


def load_zoning_js() -> dict[str, dict]:
    """zoning.js REGIONS 에서 도시명→zones{key:{bcr,far}} 추출(대조용, 느슨한 파싱)."""
    txt = ZONING_JS.read_text(encoding="utf-8")
    regions: dict[str, dict] = {}
    for m in re.finditer(r'name:\s*"([^"]+)".*?zones:\s*\{(.*?)\n\s*\},', txt, re.S):
        name, body = m.group(1), m.group(2)
        zones = {}
        for zm in re.finditer(r'"(\w+)":\s*\{\s*bcr:\s*(\d+),\s*far:\s*(\d+)', body):
            zones[zm.group(1)] = {"bcr": int(zm.group(2)), "far": int(zm.group(3))}
        regions[name] = zones
    return regions


def main() -> None:
    only = sys.argv[1:]
    cities = load_graph_cities()
    zjs = load_zoning_js()

    # 도시명 → 조례명
    def cityname(law: str) -> str:
        return law.replace(" 도시계획 조례", "").replace(" 도시계획조례", "")

    targets = sorted(cities)
    if only:
        targets = [l for l in targets if any(o in l for o in only)]

    ok = miss = mismatch = 0
    for law in targets:
        rec = cities[law]
        bcr, far = rec.get("bcr", {}), rec.get("far", {})
        name = cityname(law)
        # zoning.js 대조 (도시명 부분일치)
        ref = None
        for jn, jz in zjs.items():
            if jn in name or name in jn or cityname(jn) == name:
                ref = jz; break
        status = f"건폐율 {len(bcr):2d}존 / 용적률 {len(far):2d}존"
        if not bcr or not far:
            miss += 1
            print(f"  ⚠ {name:<12} {status}  (조문 미발견/파싱실패)")
            continue
        if ref:
            diffs = []
            for k in set(bcr) & set(far) & set(ref):
                if bcr[k] != ref[k]["bcr"]:
                    diffs.append(f"{k}:bcr {bcr[k]}≠{ref[k]['bcr']}")
                if far[k] != ref[k]["far"]:
                    diffs.append(f"{k}:far {far[k]}≠{ref[k]['far']}")
            if diffs:
                mismatch += 1
                print(f"  ✗ {name:<12} {status}  불일치 {len(diffs)}: {diffs[:4]}")
            else:
                ok += 1
                print(f"  ✓ {name:<12} {status}  (zoning.js {len(set(bcr)&set(ref))}존 전부 일치)")
        else:
            print(f"  + {name:<12} {status}  (신규 — zoning.js 없음)")

    print(f"\n── {len(targets)}개 도시계획 조례 ──")
    print(f"  검증 일치: {ok}   불일치: {mismatch}   조문미발견: {miss}")


if __name__ == "__main__":
    main()
