"""기계적 카드 데이터 생성기 — 용도지역(zoning) + 조경(landscape) 전국 자동 생성.

graph.json 에서 신규 도시(기존 손큐레이션 외)의 건폐율·용적률·조경 값을 추출해
web/src/zoning_auto.js, web/src/landscape_auto.js 로 출력.
기존 17개 손큐레이션은 건드리지 않음(zoning.js/landscape.js 가 import 해서 append).

실행: python builder/gen_card_data.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_zoning import load_graph_cities, load_zoning_js, NAME2KEY  # noqa: E402
from extract_landscape import load_graph as load_land_graph, load_land_js  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "src"

# ─── 신규 기초시 행정구역 코드(시군구 5자리). 기존 17개는 자체 code 유지 ───
CITY_CODE = {
    # 경기 (41)
    "부천시": "41190", "화성시": "41590", "안산시": "41270", "남양주시": "41360",
    "안양시": "41170", "평택시": "41220", "시흥시": "41390", "파주시": "41480",
    "김포시": "41570", "의정부시": "41150", "광명시": "41210", "군포시": "41410",
    "하남시": "41450", "오산시": "41370", "양주시": "41630", "이천시": "41500",
    "구리시": "41310", "안성시": "41550", "포천시": "41650", "의왕시": "41430",
    "여주시": "41670", "동두천시": "41250", "과천시": "41290", "광주시": "41610",
    # 강원 (51)
    "춘천시": "51110", "원주시": "51130", "강릉시": "51150", "동해시": "51170",
    "태백시": "51190", "속초시": "51210", "삼척시": "51230",
    # 충북 (43)
    "충주시": "43130", "제천시": "43150",
    # 충남 (44)
    "공주시": "44150", "보령시": "44180", "아산시": "44200", "서산시": "44210",
    "논산시": "44230", "계룡시": "44250", "당진시": "44270",
    # 전북 (52)
    "군산시": "52130", "익산시": "52140", "정읍시": "52180", "남원시": "52190",
    "김제시": "52210",
    # 전남 (46)
    "목포시": "46110", "여수시": "46130", "순천시": "46150", "나주시": "46170",
    "광양시": "46230",
    # 경북 (47)
    "포항시": "47110", "경주시": "47130", "김천시": "47150", "안동시": "47170",
    "구미시": "47190", "영주시": "47210", "영천시": "47230", "상주시": "47250",
    "문경시": "47280", "경산시": "47290",
    # 경남 (48)
    "진주시": "48170", "통영시": "48220", "사천시": "48240", "김해시": "48250",
    "밀양시": "48270", "거제시": "48310", "양산시": "48330",
}

KEY2NAME = {v: k for k, v in NAME2KEY.items()}
# zones 출력 순서(zoning.js ZONE_DEFS 순)
ZONE_ORDER = list(NAME2KEY.values())
TIER_ORDER = ["t2000", "t1000", "tu1000", "tsmall", "tschool"]
TIER_SEL = {
    "t2000": "대지면적의 {}% 이상", "t1000": "대지면적의 {}% 이상",
    "tu1000": "대지면적의 {}% 이상", "tsmall": "대지면적의 {}% 이상",
    "tschool": "대지면적의 {}% 이상",
}


def cityname(law: str) -> str:
    return (law.replace(" 도시계획 조례", "").replace(" 도시계획조례", "")
               .replace(" 건축 조례", "").replace(" 건축조례", ""))


def find_sun_id(nodes, city) -> str | None:
    """도시 건축조례 일조(높이제한) 조문의 노드 id."""
    for n in nodes:
        law = n.get("law_nm", "")
        if cityname(law) != city or ("건축 조례" not in law and "건축조례" not in law):
            continue
        t = n.get("title", "")
        if "일조" in t or ("높이" in t and "제한" in t):
            return n.get("id", "")
    return None


def main() -> None:
    g = json.loads((ROOT / "data" / "graph.json").read_text(encoding="utf-8"))
    nodes = g["nodes"]

    zcities = load_graph_cities()          # {도시계획조례명: {bcr,far,bcr_art,far_art}}
    lcities = load_land_graph()            # {건축조례명: {tiers,art}}
    existing_z = {n for n in load_zoning_js()}
    existing_l = {cityname(n): None for n in load_land_js()}
    existing_codes = set(re.findall(r'code:\s*"([^"]+)"',
                                    (WEB / "zoning.js").read_text(encoding="utf-8")))

    # 코드 충돌 검증
    seen = set(existing_codes)
    for city, code in CITY_CODE.items():
        if code in seen:
            sys.exit(f"✗ 코드 충돌: {city}={code} (이미 사용중)")
        seen.add(code)

    # ── zoning_auto ──
    z_entries, z_skip = [], []
    for law, rec in sorted(zcities.items()):
        city = cityname(law)
        if city not in CITY_CODE:          # 노이즈(道·시행규칙·스텁) 또는 기존
            continue
        if any(city in e or e in city for e in existing_z):
            continue
        bcr, far = rec.get("bcr", {}), rec.get("far", {})
        # 도시화된 시는 관리·농림·자연환경 지역이 없어 12~16존이 정상(부분파싱 아님).
        # 10존 미만만 소스 이상으로 보고 스킵(별표방식 등).
        if not bcr or not far or len(bcr) < 10:
            z_skip.append(f"{city}(건폐율{len(bcr)}/용적률{len(far)})")
            continue
        zones = {}
        for k in ZONE_ORDER:
            if k in bcr and k in far:
                zones[k] = {"bcr": bcr[k], "far": far[k]}
        sun_ref = find_sun_id(nodes, city) or f"{city} 건축 조례"
        z_entries.append({
            "code": CITY_CODE[city], "name": city,
            "bcrRef": rec.get("bcr_id", ""), "farRef": rec.get("far_id", ""),
            "sunRef": sun_ref, "zones": zones,
        })

    # ── landscape_auto ──
    l_entries, l_skip = [], []
    for law, rec in sorted(lcities.items()):
        city = cityname(law)
        if city not in CITY_CODE or city in existing_l:
            continue
        tiers = rec.get("tiers", {})
        if "t2000" not in tiers:
            l_skip.append(f"{city}({tiers})")
            continue
        out_tiers = {k: {"sel": TIER_SEL[k].format(tiers[k])}
                     for k in TIER_ORDER if k in tiers}
        l_entries.append({
            "code": CITY_CODE[city], "name": city,
            "landRef": rec.get("id", ""),
            "tiers": out_tiers,
        })

    # ── JS 출력 ──
    def js_zone(e):
        zlines = ", ".join(
            f'"{k}": {{ bcr: {v["bcr"]}, far: {v["far"]} }}'
            for k, v in e["zones"].items())
        return (f'  {{ code: "{e["code"]}", name: "{e["name"]}",\n'
                f'    refs: {{ bcr: [B77, D84, "{e["bcrRef"]}"], '
                f'far: [B78, D85, "{e["farRef"]}"], '
                f'sun: [A61, AD86, "{e["sunRef"]}"] }},\n'
                f'    zones: {{ {zlines} }} }},')

    z_js = (
        "// 자동 생성 — builder/gen_card_data.py. 수동 편집 금지(재생성: 스크립트 재실행).\n"
        "// 신규 도시 용도지역 건폐율·용적률(graph 도시계획조례 본문 추출). 기존 17개는 zoning.js 손큐레이션.\n"
        'const B77 = "국토의 계획 및 이용에 관한 법률/제77조";\n'
        'const D84 = "국토의 계획 및 이용에 관한 법률 시행령/제84조";\n'
        'const B78 = "국토의 계획 및 이용에 관한 법률/제78조";\n'
        'const D85 = "국토의 계획 및 이용에 관한 법률 시행령/제85조";\n'
        'const A61 = "건축법/제61조";\n'
        'const AD86 = "건축법 시행령/제86조";\n\n'
        "export const ZONING_AUTO = [\n" + "\n".join(js_zone(e) for e in z_entries) + "\n];\n"
    )
    (WEB / "zoning_auto.js").write_text(z_js, encoding="utf-8")

    def js_land(e):
        tlines = ", ".join(f'{k}: {{ sel: "{v["sel"]}" }}' for k, v in e["tiers"].items())
        return (f'  {{ code: "{e["code"]}", name: "{e["name"]}",\n'
                f'    refs: [LA42, LD27, "{e["landRef"]}"],\n'
                f'    tiers: {{ {tlines} }} }},')

    l_js = (
        "// 자동 생성 — builder/gen_card_data.py. 수동 편집 금지.\n"
        "// 신규 도시 조경(graph 건축조례 본문 추출). 기존은 landscape.js 손큐레이션.\n"
        'const LA42 = "건축법/제42조";\n'
        'const LD27 = "건축법 시행령/제27조";\n\n'
        "export const LANDSCAPE_AUTO = [\n" + "\n".join(js_land(e) for e in l_entries) + "\n];\n"
    )
    (WEB / "landscape_auto.js").write_text(l_js, encoding="utf-8")

    print(f"✓ zoning_auto.js   — 신규 {len(z_entries)}개 도시 (스킵 {len(z_skip)}: {z_skip})")
    print(f"✓ landscape_auto.js — 신규 {len(l_entries)}개 도시 (스킵 {len(l_skip)}: {l_skip})")


if __name__ == "__main__":
    main()
