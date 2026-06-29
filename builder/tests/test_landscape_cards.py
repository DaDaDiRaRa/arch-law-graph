"""조경 카드(연면적 규모별 조경면적 %) 회귀 스냅샷 테스트.

방어선은 용도지역과 동일: frozen / extractor_sync / plausible.
골든 갱신: `pytest --update-golden`.
"""
from __future__ import annotations

import pytest

from _cards import (
    LAND_RANGE,
    extractor_landscape, live_landscape, load_golden, save_golden,
)

CARD = "landscape"


def _diff(live: dict, golden: dict) -> list[str]:
    out: list[str] = []
    for name in sorted(set(live) | set(golden)):
        lv, gv = live.get(name), golden.get(name)
        if gv is None:
            out.append(f"  + {name}: live 신규(골든에 없음)")
            continue
        if lv is None:
            out.append(f"  - {name}: 골든에 있으나 live 에서 사라짐")
            continue
        if lv.get("src") != gv.get("src"):
            out.append(f"  ~ {name}: 출처 {gv.get('src')} → {lv.get('src')}")
        lt, gt = lv["tiers"], gv["tiers"]
        for t in sorted(set(lt) | set(gt)):
            if lt.get(t) != gt.get(t):
                out.append(f"  ✗ {name}/{t}: {gt.get(t)} → {lt.get(t)}")
    return out


def test_landscape_frozen(update_golden):
    live = live_landscape()
    if update_golden:
        save_golden(CARD, live)
        pytest.skip(f"골든 갱신 완료 ({CARD}, {len(live)}개 도시)")
    golden = load_golden(CARD)
    diffs = _diff(live, golden)
    assert not diffs, (
        f"조경 카드 값이 골든 스냅샷과 다릅니다({len(diffs)}건). "
        f"의도된 변경이면 `pytest --update-golden` 으로 승인하세요:\n" + "\n".join(diffs)
    )


def test_landscape_extractor_sync():
    live = live_landscape()
    ext = extractor_landscape()
    problems: list[str] = []
    for name, rec in live.items():
        if rec["src"] not in ("extracted", "auto"):
            continue
        et = ext.get(name)
        if et is None:
            problems.append(f"  ? {name}: 추출기가 도시를 못 찾음(조례명 매칭 실패)")
            continue
        for t, v in rec["tiers"].items():
            if t in et and et[t] != v:
                problems.append(f"  ✗ {name}/{t}: 카드 {v} ≠ 추출기 {et[t]}")
    assert not problems, (
        f"커밋된 카드와 추출기 출력이 어긋납니다({len(problems)}건):\n" + "\n".join(problems)
    )


def test_landscape_plausible():
    live = live_landscape()
    bad: list[str] = []
    for name, rec in live.items():
        for t, v in rec["tiers"].items():
            if not LAND_RANGE[0] <= v <= LAND_RANGE[1]:
                bad.append(f"  🔴 {name}/{t} 조경={v}% (허용 {LAND_RANGE[0]}~{LAND_RANGE[1]})")
    assert not bad, "물리적으로 불가능한 조경 비율(추출기 garbage 의심):\n" + "\n".join(bad)
