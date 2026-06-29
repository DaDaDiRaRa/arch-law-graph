"""조경 카드(연면적 규모별 조경면적 %) 자동추출 + landscape.js 대조 검증.

graph.json 의 건축 조례 '조경' 조문(번호목록 본문)을 파싱해 도시별 tiers{key:pct} 생성.

실행: python builder/extract_landscape.py [도시...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "data" / "graph.json"
LAND_JS = ROOT / "web" / "src" / "landscape.js"


def num_m2(s: str) -> int:
    """'2천제곱미터'·'2,000제곱미터'·'200제곱미터' → ㎡ int."""
    s = s.replace(",", "")
    m = re.search(r"(\d+)천", s)
    if m:
        return int(m.group(1)) * 1000
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 0


def pct_after(seg: str) -> int | None:
    # '대지면적의 100분의 15'(분수, 퍼센트 suffix 없음) 우선 → '대지면적(의) 15퍼센트/%'.
    m = re.search(r"대지면적\s*의?\s*100분의\s*(\d+)", seg)
    if m:
        return int(m.group(1))
    m = re.search(r"대지면적\s*의?\s*(\d+)\s*(?:퍼센트|%)", seg)
    return int(m.group(1)) if m else None


def parse_landscape(content: str) -> dict[str, int]:
    """조경 조문 본문 → {tier_key: pct}."""
    out: dict[str, int] = {}
    # 번호 항목/문장 단위로 분리
    segs = re.split(r"(?:\n|^)\s*\d+\.\s|<개정[^>]*>|①|②|③|④|⑤", content)
    for seg in segs:
        p = pct_after(seg)
        if p is None:
            continue
        if "학교이적지" in seg and "tschool" not in out:
            out["tschool"] = p
            continue
        # 대지 200~300 소규모
        if "200" in seg and "300" in seg and "미만" in seg and "tsmall" not in out:
            out["tsmall"] = p
            continue
        # 공장·물류·창고는 별도(대개 낮은) 기준 → 일반 건축물 연면적 tier 에서 제외
        if "공장" in seg or "물류" in seg:
            continue
        # 연면적 구간
        has_2000 = ("2천" in seg or "2,000" in seg or "2000" in seg)
        has_1000 = ("1천" in seg or "1,000" in seg or "1000" in seg)
        if has_2000 and "이상" in seg and "미만" not in seg.split("이상")[0]:
            if has_1000 and "미만" in seg:        # 1천 이상 2천 미만
                out.setdefault("t1000", p)
            else:                                  # 2천 이상
                out.setdefault("t2000", p)
        elif has_1000 and "미만" in seg and "이상" not in seg:
            out.setdefault("tu1000", p)           # 1천 미만
        elif has_1000 and "이상" in seg and has_2000:
            out.setdefault("t1000", p)
    return out


def load_graph() -> dict[str, dict]:
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for n in g["nodes"]:
        law = n.get("law_nm", "")
        if "건축 조례" not in law and "건축조례" not in law:
            continue
        title = n.get("title", "")
        if "조경" not in title:
            continue
        parsed = parse_landscape(n.get("content", ""))
        if parsed:
            rec = out.setdefault(law, {})
            if len(parsed) >= len(rec.get("tiers", {})):
                rec["tiers"], rec["art"], rec["id"] = parsed, n.get("article_no", ""), n.get("id", "")
    return out


def load_land_js() -> dict[str, dict]:
    txt = LAND_JS.read_text(encoding="utf-8")
    regions: dict[str, dict] = {}
    for m in re.finditer(r'name:\s*"([^"]+)".*?tiers:\s*\{(.*?)\n\s*\},', txt, re.S):
        name, body = m.group(1), m.group(2)
        tiers = {}
        for tm in re.finditer(r'(\w+):\s*\{\s*sel:\s*"[^"]*?(\d+)%', body):
            tiers[tm.group(1)] = int(tm.group(2))
        regions[name] = tiers
    return regions


def main() -> None:
    only = sys.argv[1:]
    cities = load_graph()
    ljs = load_land_js()

    def cityname(law: str) -> str:
        return law.replace(" 건축 조례", "").replace(" 건축조례", "")

    targets = sorted(cities)
    if only:
        targets = [l for l in targets if any(o in l for o in only)]

    ok = miss = mismatch = new = 0
    for law in targets:
        tiers = cities[law].get("tiers", {})
        name = cityname(law)
        ref = next((v for jn, v in ljs.items() if cityname(jn) == name), None)
        status = f"{len(tiers)}구간 {tiers}"
        if not tiers:
            miss += 1
            print(f"  ⚠ {name:<12} 파싱실패")
            continue
        if ref:
            diffs = [f"{k}:{tiers[k]}≠{ref[k]}" for k in set(tiers) & set(ref) if tiers[k] != ref[k]]
            if diffs:
                mismatch += 1
                print(f"  ✗ {name:<12} {status}  불일치: {diffs}")
            else:
                ok += 1
                print(f"  ✓ {name:<12} {status}")
        else:
            new += 1
            print(f"  + {name:<12} {status}")

    print(f"\n── {len(targets)}개 건축 조례(조경) ──")
    print(f"  일치: {ok}  불일치: {mismatch}  신규: {new}  파싱실패: {miss}")


if __name__ == "__main__":
    main()
