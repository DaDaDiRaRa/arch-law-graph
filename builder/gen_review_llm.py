"""건축위원회 심의 대상 카드 LLM 보조 생성기 (신규 일반시 = 단일 위원회 local).

graph 의 도시 건축조례 '건축위원회 심의대상'(영 제5조의5①8호) 조문을 Claude 에 주고,
설계 착수 시 확인할 심의대상 체크리스트(local[]) 추출.

실행:
  python builder/gen_review_llm.py --check 천안 청주
  python builder/gen_review_llm.py            # 신규 도시 → review_auto.js
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

SYS = """당신은 한국 지자체 건축조례의 '건축위원회 심의대상'(시행령 제5조의5제1항제8호 위임) 조문에서
설계자가 확인할 심의대상 체크리스트를 추출하는 전문가입니다.
주어진 조문 원문만 근거로, 그 도시에서 추가로 건축위원회 심의를 받아야 하는 건축물을 규모·용도 기준으로
간결한 항목(각 한 줄)으로 정리하세요. 법정 공통 심의(분양건축물·다중이용 구조안전 등 전국 동일)는 제외하고,
그 도시 조례가 정한 규모·용도·지역 기준만 추출. 삭제된 항목은 제외.
오직 JSON만 출력: {"local": ["...", "..."]}"""

PROMPT = """[도시] {city}
[건축조례 건축위원회 심의대상 조문 원문]
{article}

위 조문에서 도시가 정한 심의대상을 간결한 체크리스트로. JSON만:
{{"local": ["...", "..."]}}"""


def load_nodes():
    return json.loads((ROOT / "data" / "graph.json").read_text(encoding="utf-8"))["nodes"]


_BAD_TITLE = ("소위원회", "민원전문위원회", "전문위원회", "회의록", "비치")
_GOOD_TITLE = ("심의대상", "심의 대상", "심의사항")


def _title_spec(t: str) -> int:
    """제목 기반 특이성 점수 (높을수록 실제 심의대상 조문)."""
    if any(kw in t for kw in _GOOD_TITLE):
        return 4  # 심의대상/심의사항이 제목에 명시
    if "기능" in t or ("심의" in t and "등" in t):
        return 3  # 건축위원회 기능, 심의 등
    if any(kw in t for kw in _BAD_TITLE):
        return 1  # 소위원회·전문위원회 등 부속 조문
    return 2


def gather(nodes, city):
    """심의대상 조문(영 제5조의5 8호 언급 + 심의대상) 본문 + ref id.

    우선순위 정렬: (score DESC, title_spec DESC, len DESC)
    score 3 — 제목(위원회/심의) + 내용 모두 매칭
    score 2 — 내용에만 명시적 심의대상 키워드
    score 1 — 제목만 매칭 + 내용 200자 이상

    content_ok 키워드:
      심의대상/심의 대상/심의를 거쳐야/심의를 받아야 — 직접 표현
      제5조의5제1항제8호 — 위임근거 명시 (§5조의5.①.8호에 따라 xxx 심의한다)
      제5조의5제1항에   — 기능 조문형 위임 (§5조의5.①에 따라 위원회는 다음 각 호를 심의)
    """
    candidates: list[tuple[int, int, int, str, str]] = []  # (score, spec, len, content, id)
    for n in nodes:
        law = n.get("law_nm", "")
        if city not in law or ("건축 조례" not in law and "건축조례" not in law):
            continue
        t, c = n.get("title", ""), n.get("content", "") or ""
        title_ok = "위원회" in t or "심의" in t
        content_ok = ("심의대상" in c or "심의 대상" in c
                      or "심의를 거쳐야" in c or "심의를 받아야" in c
                      or "제5조의5제1항제8호" in c
                      or "제5조의5제1항에" in c)  # 기능 조문형 위임 표현
        if title_ok and content_ok:
            score = 3
        elif content_ok:
            score = 2
        elif title_ok and len(c) > 200:
            score = 1
        else:
            continue
        candidates.append((score, _title_spec(t), len(c), c, n.get("id", "")))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return (candidates[0][3], candidates[0][4])


def extract(client, city, art):
    msg = client.messages.create(
        model=MODEL, max_tokens=1500, temperature=0, system=SYS,
        messages=[{"role": "user", "content": PROMPT.format(city=city, article=art[:5000])}])
    m = re.search(r"\{.*\}", msg.content[0].text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def write_js(entries):
    def je(e):
        items = ",\n      ".join(f'"{x}"' for x in e["local"])
        return (f'  {{ code: "{e["code"]}", name: "{e["name"]}", ref: "{e["ref"]}",\n'
                f'    local: [\n      {items},\n    ] }},')
    out = (
        "// 자동 생성(LLM 보조) — builder/gen_review_llm.py. 신규 일반시 건축위원회 심의대상(단일 위원회).\n"
        "// graph 건축조례 심의대상 조문 → Claude 추출. 법정 공통심의는 REVIEW_NATIONAL 별도. 검토 권장.\n"
        "export const REVIEW_AUTO = [\n" + "\n".join(je(e) for e in entries) + "\n];\n"
    )
    (WEB / "review_auto.js").write_text(out, encoding="utf-8")


def main():
    args = sys.argv[1:]
    nodes = load_nodes()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if args and args[0] == "--check":
        for city in args[1:]:
            src = gather(nodes, city)
            if not src:
                print(f"  ✗ {city}: 조문 없음"); continue
            data = extract(client, city, src[0])
            print(f"\n===== {city} ({src[1]}) =====")
            for x in (data or {}).get("local", []):
                print("  •", x)
        return
    entries = []
    for city in CITY_CODE:
        src = gather(nodes, city)
        if not src:
            print(f"  · {city}: 조문 없음"); continue
        data = extract(client, city, src[0])
        if not data or not data.get("local"):
            print(f"  ✗ {city}: 추출 실패"); continue
        entries.append({"code": CITY_CODE[city], "name": city, "ref": src[1], "local": data["local"]})
        print(f"  ✓ {city}: {len(data['local'])}항목")
    write_js(entries)
    print(f"\n✓ review_auto.js — 신규 {len(entries)}개 도시")


if __name__ == "__main__":
    main()
