"""용도지역 카드(건폐율·용적률) 회귀 스냅샷 테스트.

세 방어선:
  1) test_zoning_frozen        — live 카드 값이 골든 스냅샷과 동일(사람 승인 없는 변경 차단).
  2) test_zoning_extractor_sync — 추출기 재실행값이 커밋된 카드와 일치(추출기 수정/graph 재빌드 드리프트 검출).
  3) test_zoning_plausible      — 모든 값이 물리적 허용범위(건폐율 garbage 즉시 검출).

골든 갱신: `pytest --update-golden` (값이 의도대로 바뀌었음을 사람이 승인할 때만).
"""
from __future__ import annotations

import pytest

from _cards import (
    BCR_RANGE, FAR_RANGE,
    extractor_zoning, live_zoning, load_golden, save_golden,
)

CARD = "zoning"


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
        lz, gz = lv["zones"], gv["zones"]
        for z in sorted(set(lz) | set(gz)):
            if lz.get(z) != gz.get(z):
                out.append(f"  ✗ {name}/{z}: {gz.get(z)} → {lz.get(z)}")
    return out


def test_zoning_frozen(update_golden):
    """live 카드 값이 골든과 일치해야 한다."""
    live = live_zoning()
    if update_golden:
        save_golden(CARD, live)
        pytest.skip(f"골든 갱신 완료 ({CARD}, {len(live)}개 도시)")
    golden = load_golden(CARD)
    diffs = _diff(live, golden)
    assert not diffs, (
        f"용도지역 카드 값이 골든 스냅샷과 다릅니다({len(diffs)}건). "
        f"의도된 변경이면 `pytest --update-golden` 으로 승인하세요:\n" + "\n".join(diffs)
    )


def test_zoning_extractor_sync():
    """추출기(graph.json) 재실행값이 커밋된 카드와 일치해야 한다(hwp/manual 제외)."""
    live = live_zoning()
    ext = extractor_zoning()
    problems: list[str] = []
    for name, rec in live.items():
        if rec["src"] not in ("extracted", "auto"):
            continue
        ez = ext.get(name)
        if ez is None:
            problems.append(f"  ? {name}: 추출기가 도시를 못 찾음(조례명 매칭 실패)")
            continue
        for z, v in rec["zones"].items():
            if z in ez and ez[z] != v:
                problems.append(f"  ✗ {name}/{z}: 카드 {v} ≠ 추출기 {ez[z]}")
    assert not problems, (
        f"커밋된 카드와 추출기 출력이 어긋납니다({len(problems)}건) — "
        f"추출기 수정 또는 graph 재빌드 후 카드 미재생성 가능성:\n" + "\n".join(problems)
    )


def test_zoning_plausible():
    """모든 값이 물리적 허용범위 안에 있어야 한다."""
    live = live_zoning()
    bad: list[str] = []
    for name, rec in live.items():
        for z, v in rec["zones"].items():
            if not BCR_RANGE[0] <= v["bcr"] <= BCR_RANGE[1]:
                bad.append(f"  🔴 {name}/{z} 건폐율={v['bcr']} (허용 {BCR_RANGE[0]}~{BCR_RANGE[1]})")
            if not FAR_RANGE[0] <= v["far"] <= FAR_RANGE[1]:
                bad.append(f"  🔴 {name}/{z} 용적률={v['far']} (허용 {FAR_RANGE[0]}~{FAR_RANGE[1]})")
    assert not bad, "물리적으로 불가능한 값(추출기 garbage 의심):\n" + "\n".join(bad)
