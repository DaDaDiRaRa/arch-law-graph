"""주차 카드 LLM 보조 생성기 — 부설주차장 설치기준 별표 → uses 추출.

graph 의 도시 주차조례 '부설주차장 설치대상시설물 종류 및 설치기준' 별표(박스표)를
Claude 에 주고, 표준 용도타입별 설치기준(sel)·강화여부(strict)를 JSON 으로 추출.
표준 타입(key/label/nat)은 주입 → LLM 은 sel/strict/note 만 채움(신뢰도↑).

실행:
  python builder/gen_parking_llm.py --check 대구 부산   # 기존 도시 품질검증(대조)
  python builder/gen_parking_llm.py                      # 신규 도시 전체 → parking_auto.js
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
WEB = ROOT / "web" / "src"
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_card_data import CITY_CODE, cityname  # noqa: E402

# 표준 용도타입(주차장법 시행령 별표1 그룹) — nat=국가 baseline
USE_TYPES = [
    ("wirak", "위락시설", "시설면적 100㎡당 1대"),
    ("munhwa", "문화·집회·종교·판매·운수·의료·운동·업무·방송국·장례식장", "시설면적 150㎡당 1대"),
    ("geunsaeng", "제1·2종 근린생활시설·숙박시설", "시설면적 200㎡당 1대"),
    ("dandok", "단독주택(다가구 제외)", "50~150㎡: 1대 / 150㎡ 초과: 1+(면적−150)/100"),
    ("gongdong", "다가구·공동주택·오피스텔", "주택건설기준 제27조①에 따라 산정"),
    ("golf", "골프장·골프연습장·옥외수영장·관람장", "골프장 1홀 10대 / 골프연습장 1타석 1대 / 옥외수영장 정원 15명당 1대 / 관람장 정원 100명당 1대"),
    ("suryeon", "수련시설·공장(아파트형 제외)·발전시설", "시설면적 350㎡당 1대"),
    ("changgo", "창고시설", "시설면적 400㎡당 1대"),
    ("etc", "그 밖의 건축물", "시설면적 300㎡당 1대"),
]

SYS = """당신은 한국 지자체 주차장 조례의 '부설주차장 설치대상시설물 종류 및 설치기준' 별표에서 데이터를 추출하는 전문가입니다.
주어진 별표(표) 원문만 근거로, 아래 표준 용도타입 각각에 대해 그 도시 조례의 설치기준을 추출하세요.
- sel: 해당 용도의 도시 조례 설치기준을 간결히(예: "시설면적 67㎡당 1대"). 별표에 없으면 "국가 기준과 동일".
- strict: 국가 baseline(nat)보다 주차를 더 많이 요구하면(면적기준이 더 작으면) true, 같거나 완화면 false.
- note: 특수조건(지역구분·세대당 최소대수 등)이 있으면 한 줄로. 없으면 생략.
반드시 제공된 별표에 있는 수치만 쓰고, 추측하지 마세요. 오직 JSON만 출력."""

PROMPT = """[도시] {city}
[표준 용도타입 — 이 키들에 대해 추출]
{types}

[{city} 주차조례 부설주차 설치기준 별표 원문]
{byeolpyo}

[보조 조문(설치기준 본문)]
{article}

위 별표를 근거로 아래 JSON 스키마로만 출력:
{{"uses": [{{"key": "wirak", "sel": "...", "strict": true, "note": "..."}}, ...]}}
모든 표준 키를 포함하세요(별표에 없으면 sel="국가 기준과 동일", strict=false)."""


def load_nodes():
    g = json.loads((ROOT / "data" / "graph.json").read_text(encoding="utf-8"))
    return g["nodes"]


def gather(nodes, city) -> tuple[str, str, str] | None:
    """(부설주차 별표 본문, 설치기준 조문 본문, 별표 ref id)."""
    bp = art = bp_id = ""
    for n in nodes:
        law = n.get("law_nm", "")
        if city not in law or "주차" not in law:
            continue
        t, a, c = n.get("title", ""), str(n.get("article_no", "")), n.get("content", "") or ""
        if "별표" in a and ("설치대상시설물" in t or "설치기준" in t) and len(c) > len(bp):
            bp, bp_id = c, n.get("id", "")
        if "부설주차장의 설치기준" in t and "별표" not in a and len(c) > len(art):
            art = c
    return (bp, art, bp_id) if bp else None


def extract(client, city, bp, art) -> dict | None:
    types = "\n".join(f"- {k}: {lbl} (국가 {nat})" for k, lbl, nat in USE_TYPES)
    msg = client.messages.create(
        model=MODEL, max_tokens=2000, temperature=0,
        system=SYS,
        messages=[{"role": "user", "content": PROMPT.format(
            city=city, types=types, byeolpyo=bp[:6000], article=art[:1500])}],
    )
    txt = msg.content[0].text
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def build_entry(city, code, bp_id, data) -> dict:
    lbl = {k: l for k, l, _ in USE_TYPES}
    nat = {k: n for k, _, n in USE_TYPES}
    by = {u["key"]: u for u in data.get("uses", [])}
    uses = []
    for k, _, _ in USE_TYPES:
        u = by.get(k, {})
        e = {"key": k, "label": lbl[k], "nat": nat[k],
             "sel": u.get("sel", "국가 기준과 동일"), "strict": bool(u.get("strict"))}
        if u.get("note"):
            e["note"] = u["note"]
        uses.append(e)
    return {"code": code, "name": city, "bpRef": bp_id, "uses": uses}


def main() -> None:
    args = sys.argv[1:]
    check = []
    if args and args[0] == "--check":
        check = args[1:]

    nodes = load_nodes()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    if check:
        for city in check:
            src = gather(nodes, city)
            if not src:
                print(f"  ✗ {city}: 별표 소스 없음")
                continue
            bp, art, bp_id = src
            data = extract(client, city, bp, art)
            print(f"\n===== {city} (별표 {len(bp)}자) =====")
            for u in (data or {}).get("uses", []):
                print(f"  {u['key']:<10} sel={u.get('sel')}  strict={u.get('strict')}"
                      + (f"  note={u['note']}" if u.get('note') else ""))
        return

    # 신규 도시 전체
    targets = [c for c in CITY_CODE]
    entries = []
    for city in targets:
        src = gather(nodes, city)
        if not src:
            print(f"  · {city}: 별표 없음(스킵)")
            continue
        bp, art, bp_id = src
        data = extract(client, city, bp, art)
        if not data:
            print(f"  ✗ {city}: 추출 실패")
            continue
        entries.append(build_entry(city, CITY_CODE[city], bp_id, data))
        print(f"  ✓ {city}: {len(data.get('uses', []))} uses")

    write_js(entries)
    print(f"\n✓ parking_auto.js — 신규 {len(entries)}개 도시")


def write_js(entries):
    def js(e):
        uses = ",\n      ".join(
            "{ " + f'key: "{u["key"]}", label: "{u["label"]}", nat: "{u["nat"]}", '
            f'sel: "{u["sel"]}", strict: {str(u["strict"]).lower()}'
            + (f', note: "{u["note"]}"' if u.get("note") else "") + " }"
            for u in e["uses"])
        return (f'  {{ code: "{e["code"]}", name: "{e["name"]}",\n'
                f'    refs: [PK, PK_D, PK_BP, "{e["bpRef"]}"],\n'
                f'    uses: [\n      {uses},\n    ] }},')
    out = (
        "// 자동 생성(LLM 보조) — builder/gen_parking_llm.py. 신규 도시 부설주차 설치기준.\n"
        "// graph 주차조례 별표(부설주차장 설치대상시설물) → Claude 추출. 검토 권장.\n"
        'const PK = "주차장법/제19조";\n'
        'const PK_D = "주차장법 시행령/제6조";\n'
        'const PK_BP = "주차장법 시행령/별표1";\n\n'
        "export const PARKING_AUTO = [\n" + "\n".join(js(e) for e in entries) + "\n];\n"
    )
    (WEB / "parking_auto.js").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
