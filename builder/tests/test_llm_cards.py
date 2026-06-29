"""LLM 보조 카드(주차·이격·심의·완화) 동결 스냅샷 테스트.

이 카드들은 claude-sonnet temp0 이 graph 별표/조문에서 추출 → `*_auto.js`(+손큐레이션 `*.js`).
LLM 출력이라 결정적 재현이 불가 → extractor_sync 대신 **frozen 스냅샷**으로 사람 미승인 변경만 차단.
incentive 의 items 는 함수 호출(relax/gg/green)로 생성되므로 Node(dump_cards.mjs)로 실제 평가해 비교.

  - test_llm_cards_frozen      : live(Node 덤프) == 골든. 값 바뀌면 `pytest --update-golden` 으로 승인.
  - test_llm_cards_structural  : 카드별 구조 불변식(빈 region·빈 uses 등 깨진 재생성 검출).
  - test_llm_cards_plausible   : 주차 ㎡/대·이격 m 수치가 물리적 허용범위.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from _cards import load_golden, save_golden

HERE = Path(__file__).resolve().parent
DUMP = HERE / "dump_cards.mjs"
CARD = "cards_llm"

PARK_RANGE = (30, 2000)   # 시설면적 N㎡당 1대 (위락 67 ~ 학생기숙사 400+)
SETBACK_RANGE = (0.0, 20.0)  # 이격 거리 N m


def _dump_cards() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node 미설치 — LLM 카드 동결 테스트 건너뜀(결정적 카드 테스트는 실행됨)")
    r = subprocess.run([node, str(DUMP)], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        pytest.fail(f"dump_cards.mjs 실행 실패:\n{r.stderr}")
    return json.loads(r.stdout)


def _diff(live, golden, path: str = "") -> list[str]:
    """JSON 트리 재귀 비교 → 변경 경로 목록."""
    out: list[str] = []
    if type(live) is not type(golden):
        out.append(f"  {path or '<root>'}: 타입 {type(golden).__name__}→{type(live).__name__}")
        return out
    if isinstance(golden, dict):
        for k in sorted(set(golden) | set(live)):
            if k not in golden:
                out.append(f"  {path}.{k}: 신규 키")
            elif k not in live:
                out.append(f"  {path}.{k}: 삭제됨")
            else:
                out += _diff(live[k], golden[k], f"{path}.{k}")
    elif isinstance(golden, list):
        if len(golden) != len(live):
            out.append(f"  {path}: 길이 {len(golden)}→{len(live)}")
        for i in range(min(len(golden), len(live))):
            out += _diff(live[i], golden[i], f"{path}[{i}]")
    elif golden != live:
        out.append(f"  {path}: {golden!r} → {live!r}")
    return out


def test_llm_cards_frozen(update_golden):
    live = _dump_cards()
    if update_golden:
        save_golden(CARD, live)
        pytest.skip(f"골든 갱신 완료 ({CARD})")
    golden = load_golden(CARD)
    diffs = _diff(live, golden)
    assert not diffs, (
        f"LLM 카드(주차·이격·심의·완화) 값이 골든 스냅샷과 다릅니다({len(diffs)}건). "
        f"의도된 변경이면 `pytest --update-golden` 으로 승인하세요:\n" + "\n".join(diffs[:40])
    )


def test_llm_cards_structural():
    d = _dump_cards()
    bad: list[str] = []
    for r in d["parking"]:
        if not r.get("code") or not r.get("name"):
            bad.append(f"  parking {r.get('name', r)}: code/name 누락")
        elif not r.get("uses"):
            bad.append(f"  parking {r['name']}: uses 비어있음")
    for r in d["setback"]:
        if not r.get("code") or not r.get("name"):
            bad.append(f"  setback {r.get('name', r)}: code/name 누락")
        elif not r.get("uses"):
            bad.append(f"  setback {r['name']}: uses 비어있음")
    for r in d["review"]["regions"]:
        if not r.get("code") or not r.get("name"):
            bad.append(f"  review {r.get('name', r)}: code/name 누락")
        elif not (r.get("si") or r.get("gu") or r.get("local")):
            bad.append(f"  review {r['name']}: si/gu/local 전부 비어있음")
    if not d["review"]["national"]:
        bad.append("  review national: 비어있음")
    for r in d["incentive"]:
        if not r.get("code") or not r.get("name"):
            bad.append(f"  incentive {r.get('name', r)}: code/name 누락")
        elif not r.get("items"):
            bad.append(f"  incentive {r['name']}: items 비어있음")
    assert not bad, "LLM 카드 구조 불변식 위반(깨진 재생성 의심):\n" + "\n".join(bad)


def test_llm_cards_plausible():
    d = _dump_cards()
    bad: list[str] = []

    # 주차: '시설면적 N㎡당 1대' 의 N 검사(패턴 일치하는 값만).
    for r in d["parking"]:
        for u in r["uses"]:
            for fld in ("nat", "sel"):
                for m in re.finditer(r"(\d[\d,]*)\s*㎡당", u.get(fld, "") or ""):
                    n = int(m.group(1).replace(",", ""))
                    if not PARK_RANGE[0] <= n <= PARK_RANGE[1]:
                        bad.append(f"  🔴 주차 {r['name']}/{u['key']}.{fld}: {n}㎡당 (허용 {PARK_RANGE})")

    # 이격: 'N m' 거리 검사(liner/boundary 의 nat/sel 문자열).
    for r in d["setback"]:
        for u in r["uses"]:
            for axis in ("liner", "boundary"):
                ax = u.get(axis) or {}
                for fld in ("nat", "sel"):
                    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*m(?![²㎡])", ax.get(fld, "") or ""):
                        v = float(m.group(1))
                        if not SETBACK_RANGE[0] <= v <= SETBACK_RANGE[1]:
                            bad.append(f"  🔴 이격 {r['name']}/{u['key']}.{axis}.{fld}: {v}m (허용 {SETBACK_RANGE})")

    assert not bad, "물리적으로 불가능한 주차·이격 수치(LLM garbage 의심):\n" + "\n".join(bad[:30])
