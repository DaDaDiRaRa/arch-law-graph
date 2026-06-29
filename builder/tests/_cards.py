"""카드 회귀 테스트 공유 헬퍼 — JS 카드 파싱 + 추출기 래퍼 + 골든 입출력.

용어:
  live     : web/src 의 *.js + *_auto.js 에서 실제 렌더되는 값(사용자가 보는 값).
  extractor: builder/extract_*.py 가 graph.json 에서 재추출한 값(빌드 파이프라인).
  golden   : tests/golden/*.json — 사람이 승인한 고정 스냅샷(회귀 기준선).

출처(src) 태그 — 각 도시 값의 신뢰 근거(로드맵 C-2 배지의 씨앗):
  extracted : 손큐레이션이지만 추출기가 그대로 재현 → 일관성 검사 대상.
  hwp       : 손큐레이션, 원문이 HWP 별표라 정규식 추출기로 도달 불가 → 일관성 검사 제외.
  manual    : 손큐레이션, 추출기가 오파싱(신뢰불가) → 손검증값 채택, 일관성 검사 제외.
  auto      : 기계 자동생성(gen_card_data.py) → 추출기 일관성 검사 대상.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WEB = ROOT / "web" / "src"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

# ── 추출기로 검증할 수 없는 손큐레이션 도시(원문이 HWP 별표거나 추출기 오파싱) ──
ZONING_HWP = {"울산광역시", "창원시"}   # 도시계획조례 건폐율·용적률이 별표(HWP)
ZONING_MANUAL = {"전주시"}             # 추출기가 숫자 연결 오파싱(402 등) → 손검증값 채택
LANDSCAPE_HWP: set[str] = set()
LANDSCAPE_MANUAL = {"전주시"}          # 조경 t2000 추출 15 vs 손검증 18(다단계 조문)

# ── 타당성 경계(물리적으로 불가능한 값 = 추출기 garbage 즉시 검출) ──
BCR_RANGE = (20, 90)      # 건폐율 %: 녹지 20 ~ 중심상업 90
FAR_RANGE = (50, 1500)    # 용적률 %: 녹지 50 ~ 중심상업 1500
LAND_RANGE = (3, 30)      # 조경 %: 소규모 ~ 학교이적지 30


# ───────────────────────── JS 카드 파싱 ─────────────────────────
def _blocks(text: str):
    """`code: "X", name: "Y"` 헤더로 도시 블록 분할 → [(code, name, block_text)].

    ZONE_DEFS/TIER_DEFS(헤더 없음)는 자동 제외됨.
    """
    heads = list(re.finditer(r'code:\s*"([^"]+)",\s*name:\s*"([^"]+)"', text))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        yield h.group(1), h.group(2), text[h.end():end]


def _parse_zoning_file(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    text = path.read_text(encoding="utf-8")
    for code, name, block in _blocks(text):
        zones = {}
        for zm in re.finditer(r'"(\w+)":\s*\{\s*bcr:\s*(\d+),\s*far:\s*(\d+)', block):
            zones[zm.group(1)] = {"bcr": int(zm.group(2)), "far": int(zm.group(3))}
        out[name] = {"code": code, "zones": zones}
    return out


def _parse_landscape_file(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    text = path.read_text(encoding="utf-8")
    for code, name, block in _blocks(text):
        tiers = {}
        for tm in re.finditer(r'(\w+):\s*\{\s*sel:\s*"[^"]*?(\d+)\s*%', block):
            tiers[tm.group(1)] = int(tm.group(2))
        out[name] = {"code": code, "tiers": tiers}
    return out


def live_zoning() -> dict[str, dict]:
    """zoning.js(손큐) + zoning_auto.js(자동) 병합. {name: {code, src, zones}}."""
    curated = _parse_zoning_file(WEB / "zoning.js")
    auto = _parse_zoning_file(WEB / "zoning_auto.js")
    merged: dict[str, dict] = {}
    for name, rec in curated.items():
        src = "hwp" if name in ZONING_HWP else "manual" if name in ZONING_MANUAL else "extracted"
        merged[name] = {**rec, "src": src}
    for name, rec in auto.items():
        merged.setdefault(name, {**rec, "src": "auto"})
    return merged


def live_landscape() -> dict[str, dict]:
    curated = _parse_landscape_file(WEB / "landscape.js")
    auto = _parse_landscape_file(WEB / "landscape_auto.js")
    merged: dict[str, dict] = {}
    for name, rec in curated.items():
        src = "hwp" if name in LANDSCAPE_HWP else "manual" if name in LANDSCAPE_MANUAL else "extracted"
        merged[name] = {**rec, "src": src}
    for name, rec in auto.items():
        merged.setdefault(name, {**rec, "src": "auto"})
    return merged


# ───────────────────────── 추출기 재실행(graph.json) ─────────────────────────
def _cityname(law: str) -> str:
    return (law.replace(" 도시계획 조례", "").replace(" 도시계획조례", "")
               .replace(" 건축 조례", "").replace(" 건축조례", ""))


def extractor_zoning() -> dict[str, dict]:
    """graph.json → {cityname: {zone: {bcr, far}}}. 변종 조례명은 존 수 많은 쪽 채택."""
    from extract_zoning import load_graph_cities  # noqa: E402
    out: dict[str, dict] = {}
    for law, rec in load_graph_cities().items():
        city = _cityname(law)
        bcr, far = rec.get("bcr", {}), rec.get("far", {})
        zones = {k: {"bcr": bcr[k], "far": far[k]} for k in bcr if k in far}
        if city not in out or len(zones) > len(out[city]):
            out[city] = zones
    return out


def extractor_landscape() -> dict[str, dict]:
    """graph.json → {cityname: {tier: pct}}."""
    from extract_landscape import load_graph  # noqa: E402
    out: dict[str, dict] = {}
    for law, rec in load_graph().items():
        city = _cityname(law)
        tiers = dict(rec.get("tiers", {}))
        if city not in out or len(tiers) > len(out[city]):
            out[city] = tiers
    return out


# ───────────────────────── 골든 입출력 ─────────────────────────
def golden_path(card: str) -> Path:
    return GOLDEN_DIR / f"{card}.json"


def load_golden(card: str) -> dict:
    return json.loads(golden_path(card).read_text(encoding="utf-8"))


def save_golden(card: str, data: dict) -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    golden_path(card).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
