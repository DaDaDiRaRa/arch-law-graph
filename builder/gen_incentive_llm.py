"""완화·혜택 카드 LLM 보조 생성기 — 공개공지(gg) + 친환경 재정지원(green) 도시별 추출.

용적률완화(relax)·부설주차면제(PARKING_EXEMPT)는 전국 공통(시행령 위임값) → 공유 헬퍼 그대로.
도시별 변동만 추출: 공개공지 대상/면적(건축조례), 친환경 재정지원(녹색건축 조례).
incentive_auto.js 는 incentive_helpers.js 의 헬퍼를 import 해 entries 구성(순환 import 회피).

실행:
  python builder/gen_incentive_llm.py --check 대구
  python builder/gen_incentive_llm.py          # 신규 도시 → incentive_auto.js
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
from gen_card_data import CITY_CODE  # noqa: E402
from extract_zoning import load_graph_cities  # noqa: E402

SYS = """당신은 한국 지자체 건축조례·녹색건축물조례에서 완화·혜택 데이터를 추출하는 전문가입니다.
주어진 두 조문 원문만 근거로 아래를 추출하세요.
- gg_target: 공개공지 확보 대상 건축물(용도·규모). 예: "법정 6종 + 의료·운동·위락·장례식장 (5천㎡↑)".
- gg_area: 확보 면적 비율. 예: "대지면적의 10%" 또는 "5천~1만㎡ 5% / 1만~3만㎡ 7% / 3만㎡↑ 10%".
- gg_area_strict: 국가 baseline(10% 한도)보다 강화·구체화면 true.
- green_fiscal: 녹색건축 조례의 재정지원 내용 한 줄. 예: "그린리모델링기금 / 시범·인증비용 지원". 없으면 "시범사업·인증비용 지원".
조문에 없으면 합리적 기본값. 오직 JSON만 출력."""

PROMPT = """[도시] {city}
[건축조례 공개공지 조문]
{gg_art}

[녹색건축물 조성 지원 조례(재정지원)]
{green_art}

JSON만:
{{"gg_target": "...", "gg_area": "...", "gg_area_strict": true, "green_fiscal": "..."}}"""


def load_nodes():
    return json.loads((ROOT / "data" / "graph.json").read_text(encoding="utf-8"))["nodes"]


def gather(nodes, city):
    """(공개공지 조문본문, 공개공지 ref, 녹색 조문본문, 녹색 ref).

    공개공지 면적기준은 '공개공지 등의 확보' 조문에 있음. 제목에 '공개공지'가 들어가는
    '안내판 설치기준'·'관리대장' 별표가 본문이 더 길어 오선택되는 문제를 점수로 회피:
    면적 비율(퍼센트/100분의/%) 보유 + 조문(article)일수록 우선.
    """
    gg_c = gg_id = gr_c = gr_id = ""
    gg_score = -1
    for n in nodes:
        law = n.get("law_nm", "")
        # 부분문자열 오매칭 방지(예: "양주시" ⊄ "남양주시 건축 조례"). 도시명은 접두 또는 공백 뒤에만 인정.
        if not re.search(r"(?:^|\s)" + re.escape(city), law):
            continue
        t, c = n.get("title", ""), n.get("content", "") or ""
        if ("건축 조례" in law or "건축조례" in law) and "공개공지" in (t + c[:200]).replace(" ", ""):
            if "안내판" not in t and "관리대장" not in t:
                has_ratio = bool(re.search(r"(100분의|퍼센트|%)", c))
                is_article = n.get("type") == "article"
                score = (2 if has_ratio else 0) + (1 if is_article else 0)
                if score > gg_score or (score == gg_score and len(c) > len(gg_c)):
                    gg_c, gg_id, gg_score = c, n.get("id", ""), score
        if "녹색건축물" in law and ("지원" in t or "재정" in c or "기금" in c or "보조" in c) and len(c) > len(gr_c):
            gr_c, gr_id = c, n.get("id", "")
    return gg_c, gg_id, gr_c, gr_id


def extract(client, city, gg_c, gr_c):
    msg = client.messages.create(
        model=MODEL, max_tokens=1200, temperature=0, system=SYS,
        messages=[{"role": "user", "content": PROMPT.format(
            city=city, gg_art=gg_c[:3500] or "(없음)", green_art=gr_c[:2500] or "(없음)")}])
    m = re.search(r"\{.*\}", msg.content[0].text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def esc(s: str) -> str:
    return (s or "").replace("\\", "").replace('"', "'").strip()


def write_js(entries):
    def je(e):
        opts = ', { areaStrict: true }' if e["gg_area_strict"] else ""
        items = [
            f'relax("{e["relaxRef"]}")',
            f'gg("{e["ggRef"]}", "{esc(e["gg_target"])}", "{esc(e["gg_area"])}"{opts})',
            f'green("{e["greenRef"]}", "{esc(e["green_fiscal"])}")',
            "PARKING_EXEMPT",
        ]
        items_js = ",\n    ".join(items)
        return (f'  {{ code: "{e["code"]}", name: "{e["name"]}", items: [\n'
                f'    {items_js},\n  ] }},')
    out = (
        "// 자동 생성(LLM 보조) — builder/gen_incentive_llm.py. 신규 도시 완화·혜택.\n"
        "// 용적률완화·부설주차면제는 전국 공통 헬퍼. 공개공지·재정지원만 도시별 추출. 검토 권장.\n"
        'import { gg, green, relax, PARKING_EXEMPT } from "./incentive_helpers.js";\n\n'
        "export const BENEFIT_AUTO = [\n" + "\n".join(je(e) for e in entries) + "\n];\n"
    )
    (WEB / "incentive_auto.js").write_text(out, encoding="utf-8")


def main():
    args = sys.argv[1:]
    nodes = load_nodes()
    zc = load_graph_cities()  # 용적률 ref용
    far_id = {}
    for law, rec in zc.items():
        nm = law.replace(" 도시계획 조례", "").replace(" 도시계획조례", "")
        if rec.get("far_id"):
            far_id[nm] = rec["far_id"]
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    if args and args[0] == "--check":
        for city in args[1:]:
            gg_c, gg_id, gr_c, gr_id = gather(nodes, city)
            data = extract(client, city, gg_c, gr_c)
            print(f"\n===== {city} =====\n  gg_ref={gg_id} green_ref={gr_id}")
            print(" ", data)
        return

    entries = []
    for city in CITY_CODE:
        gg_c, gg_id, gr_c, gr_id = gather(nodes, city)
        if not gg_id and not gr_id:
            print(f"  · {city}: 소스 없음"); continue
        data = extract(client, city, gg_c, gr_c)
        if not data:
            print(f"  ✗ {city}: 추출 실패"); continue
        entries.append({
            "code": CITY_CODE[city], "name": city,
            "relaxRef": far_id.get(city, f"{city} 도시계획 조례"),
            "ggRef": gg_id or f"{city} 건축 조례",
            "greenRef": gr_id or f"{city} 녹색건축물 조성 지원 조례",
            "gg_target": data.get("gg_target", "법정 6종(문화·집회·종교·판매·운수·업무·숙박 5천㎡↑)"),
            "gg_area": data.get("gg_area", "대지면적의 10% 이하"),
            "gg_area_strict": bool(data.get("gg_area_strict")),
            "green_fiscal": data.get("green_fiscal", "시범사업·인증비용 지원"),
        })
        print(f"  ✓ {city}")
    write_js(entries)
    print(f"\n✓ incentive_auto.js — 신규 {len(entries)}개 도시")


if __name__ == "__main__":
    main()
