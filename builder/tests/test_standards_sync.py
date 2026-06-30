"""data/standards.json 단일소스 동기화 테스트 (B-6).

standards.json 은 카드 JS(web/src/*.js)의 생성물(generated artifact)이다. 사람은 JS 를 편집하고
gen_standards.mjs 가 JSON 을 동기화한다. 이 테스트는 커밋된 standards.json 이 현재 JS 와
어긋나지 않는지(=JS 수정 후 재생성을 잊지 않았는지) 검출한다.

  - test_standards_in_sync : `node gen_standards.mjs --stdout`(JS 재평가) == 커밋된 data/standards.json.
                             어긋나면 `node builder/gen_standards.mjs` 재실행 후 커밋.
  - test_standards_structural : 도메인 구조 + region code/refs/src 불변식.

⚠ 카드 값 자체의 회귀(사람 미승인 변경)는 test_zoning/landscape/llm_cards 의 frozen 골든이 잡는다.
   본 테스트는 'JSON 이 JS 와 동기 상태인가'만 본다(생성물 드리프트).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
GEN = ROOT / "builder" / "gen_standards.mjs"
STANDARDS = ROOT / "data" / "standards.json"

DOMAINS = ["zoning", "landscape", "parking", "setback", "incentive", "review"]


def _regen_stdout() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node 미설치 — standards 동기화 테스트 건너뜀")
    r = subprocess.run(
        [node, str(GEN), "--stdout"], capture_output=True, text=True, encoding="utf-8"
    )
    if r.returncode != 0:
        pytest.fail(f"gen_standards.mjs 실행 실패:\n{r.stderr}")
    return json.loads(r.stdout)


def _committed() -> dict:
    if not STANDARDS.exists():
        pytest.fail("data/standards.json 없음 — `node builder/gen_standards.mjs` 실행 후 커밋")
    return json.loads(STANDARDS.read_text(encoding="utf-8"))


def test_standards_in_sync():
    live = _regen_stdout()
    committed = _committed()
    assert live == committed, (
        "data/standards.json 이 카드 JS(web/src/*.js)와 어긋납니다. "
        "JS 수정 후 재생성을 잊었을 가능성 — `node builder/gen_standards.mjs` 실행 후 커밋하세요."
    )


def test_standards_structural():
    d = _committed()
    assert d.get("schema_version") == 1
    assert set(d["domains"]) == set(DOMAINS), "도메인 키 누락/추가"
    bad: list[str] = []
    for dom in DOMAINS:
        regions = d["domains"][dom]["regions"]
        if not regions:
            bad.append(f"  {dom}: regions 비어있음")
        for r in regions:
            if not r.get("code") or not r.get("name"):
                bad.append(f"  {dom} {r.get('name', r)}: code/name 누락")
    # 국가 정의 존재 확인
    if not d["national"]["zoning"]["zone_defs"]:
        bad.append("  national.zoning.zone_defs 비어있음")
    if not d["national"]["review"]["national"]:
        bad.append("  national.review.national 비어있음")
    assert not bad, "standards.json 구조 불변식 위반:\n" + "\n".join(bad)
