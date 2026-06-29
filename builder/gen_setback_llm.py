"""이격(대지 안의 공지) 카드 LLM 보조 생성기.

graph 의 도시 건축조례 '대지 안의 공지' 별표(박스표)를 Claude 에 주고,
표준 용도타입별 건축선(liner)·인접대지경계선(boundary) 후퇴거리(sel)·강화여부(strict) 추출.

실행:
  python builder/gen_setback_llm.py --check 부산 인천
  python builder/gen_setback_llm.py            # 신규 도시 → setback_auto.js
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

# 표준 용도타입 — (key, label, liner_nat, boundary_nat)
USE_TYPES = [
    ("gongdong", "공동주택", "아파트 2~6m / 연립 2~5m / 다세대 1~4m", "아파트 2~6m / 연립 1.5~5m / 다세대 0.5~4m"),
    ("jeonju", "전용주거지역 건축물(공동주택 제외)", "—", "1~6m"),
    ("panmae", "판매·숙박·문화집회·종교시설 등(대규모)", "1,000㎡↑: 3~6m", "1,000㎡↑(상업지역 아닌 곳): 1.5~6m"),
    ("gongjang", "공장·창고(바닥면적 500㎡↑)", "준공업 1.5~6m / 그 외 3~6m", "준공업 1~6m / 그 외 1.5~6m"),
    ("etc", "그 밖의 건축물", "1~6m", "0.5~6m"),
]

SYS = """당신은 한국 지자체 건축조례 '대지 안의 공지' 별표에서 이격거리 데이터를 추출하는 전문가입니다.
'대지 안의 공지'는 두 축이 있습니다: ① 건축선(liner)에서의 후퇴, ② 인접 대지경계선(boundary)에서의 후퇴.
주어진 별표 원문만 근거로, 표준 용도타입 각각에 대해 그 도시의 후퇴거리를 추출하세요.
- liner.sel / boundary.sel: 도시 조례의 후퇴거리(예: "준공업 1.5m↑ / 그 외 3m↑"). 별표에 그 축이 없으면 sel="해당 없음".
- strict: 국가 범위 baseline(nat)을 구체화하거나 하한을 강화하면 true.
- note: 특수조건 한 줄(있을 때만).
별표에 있는 수치만 쓰고 추측 금지. 오직 JSON만 출력."""

PROMPT = """[도시] {city}
[표준 용도타입]
{types}

[{city} 건축조례 '대지 안의 공지' 별표 원문]
{byeolpyo}

아래 JSON 스키마로만 출력(모든 표준 키 포함):
{{"uses": [{{"key": "gongdong", "liner": {{"sel": "...", "strict": true}}, "boundary": {{"sel": "...", "strict": true}}, "note": "..."}}, ...]}}"""


def load_nodes():
    g = json.loads((ROOT / "data" / "graph.json").read_text(encoding="utf-8"))
    return g["nodes"]


def gather(nodes, city):
    bp = bp_id = art_id = ""
    for n in nodes:
        law = n.get("law_nm", "")
        if city not in law or ("건축 조례" not in law and "건축조례" not in law):
            continue
        t, a, c = n.get("title", ""), str(n.get("article_no", "")), n.get("content", "") or ""
        if "별표" in a and "공지" in (t + c[:300]) and len(c) > len(bp):
            bp, bp_id = c, n.get("id", "")
        if "공지" in t and "별표" not in a and not art_id:
            art_id = n.get("id", "")
    return (bp, bp_id, art_id) if bp else None


def extract(client, city, bp):
    types = "\n".join(f"- {k}: {lbl} (국가 건축선:{ln} / 인접경계:{bn})"
                      for k, lbl, ln, bn in USE_TYPES)
    msg = client.messages.create(
        model=MODEL, max_tokens=2000, temperature=0, system=SYS,
        messages=[{"role": "user", "content": PROMPT.format(
            city=city, types=types, byeolpyo=bp[:6500])}])
    m = re.search(r"\{.*\}", msg.content[0].text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def build_entry(city, code, bp_id, art_id, data):
    lbl = {k: l for k, l, _, _ in USE_TYPES}
    lnat = {k: n for k, _, n, _ in USE_TYPES}
    bnat = {k: n for k, _, _, n in USE_TYPES}
    by = {u["key"]: u for u in data.get("uses", [])}
    uses = []
    for k, _, _, _ in USE_TYPES:
        u = by.get(k, {})
        e = {"key": k, "label": lbl[k]}
        ln, bn = u.get("liner", {}), u.get("boundary", {})
        if lnat[k] != "—":
            e["liner"] = {"nat": lnat[k], "sel": ln.get("sel", "해당 없음"), "strict": bool(ln.get("strict"))}
        e["boundary"] = {"nat": bnat[k], "sel": bn.get("sel", "해당 없음"), "strict": bool(bn.get("strict"))}
        if u.get("note"):
            e["note"] = u["note"]
        uses.append(e)
    return {"code": code, "name": city, "ref": art_id, "bpRef": bp_id, "uses": uses}


def write_js(entries):
    def jaxis(ax):
        return ('{ ' + f'nat: "{ax["nat"]}", sel: "{ax["sel"]}", strict: {str(ax["strict"]).lower()}' + ' }')

    def juse(u):
        parts = [f'key: "{u["key"]}", label: "{u["label"]}"']
        if "liner" in u:
            parts.append("liner: " + jaxis(u["liner"]))
        parts.append("boundary: " + jaxis(u["boundary"]))
        if u.get("note"):
            parts.append(f'note: "{u["note"]}"')
        return "{ " + ", ".join(parts) + " }"

    def je(e):
        uses = ",\n      ".join(juse(u) for u in e["uses"])
        return (f'  {{ code: "{e["code"]}", name: "{e["name"]}",\n'
                f'    refs: [A58, AD80, AD_BP, "{e["ref"]}", "{e["bpRef"]}"],\n'
                f'    uses: [\n      {uses},\n    ] }},')
    out = (
        "// 자동 생성(LLM 보조) — builder/gen_setback_llm.py. 신규 도시 대지안의공지(이격).\n"
        'const A58 = "건축법/제58조";\n'
        'const AD80 = "건축법 시행령/제80의2조";\n'
        'const AD_BP = "건축법 시행령/별표2";\n\n'
        "export const SETBACK_AUTO = [\n" + "\n".join(je(e) for e in entries) + "\n];\n"
    )
    (WEB / "setback_auto.js").write_text(out, encoding="utf-8")


def main():
    args = sys.argv[1:]
    nodes = load_nodes()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if args and args[0] == "--check":
        for city in args[1:]:
            src = gather(nodes, city)
            if not src:
                print(f"  ✗ {city}: 별표 없음"); continue
            data = extract(client, city, src[0])
            print(f"\n===== {city} =====")
            for u in (data or {}).get("uses", []):
                print(f"  {u['key']:<10} liner={u.get('liner',{}).get('sel')} | boundary={u.get('boundary',{}).get('sel')}")
        return
    entries = []
    for city in CITY_CODE:
        src = gather(nodes, city)
        if not src:
            print(f"  · {city}: 별표 없음"); continue
        bp, bp_id, art_id = src
        data = extract(client, city, bp)
        if not data:
            print(f"  ✗ {city}: 추출 실패"); continue
        entries.append(build_entry(city, CITY_CODE[city], bp_id, art_id, data))
        print(f"  ✓ {city}")
    write_js(entries)
    print(f"\n✓ setback_auto.js — 신규 {len(entries)}개 도시")


if __name__ == "__main__":
    main()
