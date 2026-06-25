"""법령군 fetch → 노드/엣지 추출 → data/graph.json 생성 (Phase 1 핵심).

실행: 프로젝트 루트(D:\\APPS\\arch-law-graph)에서
  <자매앱 venv>\\python.exe builder\\build_graph.py            # 법령군 전체
  <자매앱 venv>\\python.exe builder\\build_graph.py --only 건축법   # 1개만 (품질 확인)

.env 의 LAW_API_KEY 를 사용한다. 산출물: data/graph.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime

# Windows 콘솔(cp949)에서도 한글·기호 출력되도록
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networkx as nx  # noqa: E402

from law_go_kr_client import LawGoKrClient  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "graph.json")

# ─── 대상 법령군 ───────────────────────────────────────────────────────────

LAW_GROUP = [
    # 건축법 패밀리 — 본법·시행령·시행규칙 + 핵심 위임 부령(기술기준 본체)
    "건축법", "건축법 시행령", "건축법 시행규칙",
    "건축물의 피난ㆍ방화구조 등의 기준에 관한 규칙",  # 방화·피난 (ㆍ = U+318D)
    "건축물의 설비기준 등에 관한 규칙",                # 설비·승강기·환기
    "건축물의 구조기준 등에 관한 규칙",                # 구조 안전
    "건축물대장의 기재 및 관리 등에 관한 규칙",        # 대장·표제부
    # 국토계획 패밀리
    "국토의 계획 및 이용에 관한 법률",
    "국토의 계획 및 이용에 관한 법률 시행령",
    "국토의 계획 및 이용에 관한 법률 시행규칙",
    # 주차장 패밀리
    "주차장법", "주차장법 시행령", "주차장법 시행규칙",
    # 분양 패밀리 (시행령·시행규칙 추가)
    "건축물의 분양에 관한 법률",
    "건축물의 분양에 관한 법률 시행령",
    "건축물의 분양에 관한 법률 시행규칙",
    # 녹색건축 패밀리 (시행령·시행규칙 추가)
    "녹색건축물 조성 지원법",
    "녹색건축물 조성 지원법 시행령",
    "녹색건축물 조성 지원법 시행규칙",
]

# ─── domain_tags 분류 (자매 앱 진단 8카테고리) ──────────────────────────────

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "건폐율": ["건폐율", "건축면적", "대지면적"],
    "용적률": ["용적률", "연면적", "바닥면적"],
    "높이·일조": ["높이", "일조", "층수", "가로구역", "고도지구"],
    "주차": ["주차", "주차장", "부설주차"],
    "조경": ["조경", "녹지", "식재"],
    "설비·소방": ["설비", "소방", "방화", "피난", "배연", "급수", "배수", "승강기"],
    "행위제한": ["허가", "신고", "용도", "행위제한", "이격", "대지경계"],
    "도시계획시설": ["도시계획시설", "지구단위", "용도지역", "용도지구", "기반시설"],
}


def classify_domain(text: str) -> list[str]:
    """content/title 텍스트에 매칭되는 도메인 태그(복수). 0개면 ['기타']."""
    tags = [
        domain
        for domain, kws in DOMAIN_KEYWORDS.items()
        if any(kw in text for kw in kws)
    ]
    return tags or ["기타"]


# ─── 엣지 추출 regex ───────────────────────────────────────────────────────

# 같은 법령 내 조문 인용: "제12조", "제12조의3" — 항·호는 무시(조까지만 연결)
RE_ARTICLE = re.compile(r"제(\d+)조(?:의(\d+))?")
# 타 법령 인용: 「건축법」
RE_CROSS_LAW = re.compile(r"「([^」]+)」")
# 별표: "별표 1", "별표1"
RE_BYEOLPYO = re.compile(r"별표\s*(\d+)")
# 위임 표현 → (대상 법령유형, 표현)
DELEGATE_PATTERNS = [
    ("대통령령", re.compile(r"대통령령으로\s*정")),
    ("국토교통부령", re.compile(r"국토교통부령으로\s*정")),
    ("행정안전부령", re.compile(r"행정안전부령으로\s*정")),
]


def _evidence(text: str, start: int, end: int, span: int = 25) -> str:
    """매칭 위치 주변 원문 발췌(증거 보존용)."""
    a = max(0, start - span)
    b = min(len(text), end + span)
    snippet = text[a:b].replace("\n", " ").strip()
    return f"…{snippet}…"


# ─── 그래프 빌드 ───────────────────────────────────────────────────────────


def article_id(law_nm: str, article_no: str) -> str:
    """조문 노드 ID. 별표는 그대로, 일반 조문은 '제N조'."""
    if article_no.startswith("별표"):
        return f"{law_nm}/{article_no}"
    return f"{law_nm}/제{article_no}조"


def add_law_nodes(G: nx.DiGraph, law_nm: str, articles: list[dict], source_url: str) -> None:
    """law 노드 1개 + 소속 article 노드 + contains 엣지."""
    G.add_node(law_nm, type="law", law_nm=law_nm)
    for art in articles:
        art_no = art.get("article_no", "")
        if not art_no:
            continue
        nid = article_id(law_nm, art_no)
        title = art.get("title", "")
        content = art.get("content", "")
        G.add_node(
            nid,
            type="article",
            law_nm=law_nm,
            article_no=art_no,
            title=title,
            content=content,
            ef_yd=art.get("ef_yd", ""),
            domain_tags=classify_domain(f"{title}\n{content}"),
            source_url=source_url,
        )
        G.add_edge(law_nm, nid, type="contains", method="structure")


def extract_edges(
    G: nx.DiGraph, law_nm: str, articles: list[dict], known_laws: set[str]
) -> None:
    """article content 본문에서 references / cross_law / byeolpyo / delegates 추출."""
    # 이 법령이 가진 조문번호 집합 (같은 법령 내 인용 해소용)
    own_articles = {a.get("article_no", "") for a in articles if a.get("article_no")}

    for art in articles:
        art_no = art.get("article_no", "")
        if not art_no:
            continue
        src = article_id(law_nm, art_no)
        content = art.get("content", "")

        # 1) references — 같은 법령 내 조문
        for m in RE_ARTICLE.finditer(content):
            no = m.group(1)
            branch = m.group(2)
            target_no = f"{no}의{branch}" if branch else no
            if target_no == art_no:
                continue  # 자기 자신 제외
            if target_no in own_articles:
                tgt = article_id(law_nm, target_no)
                if not G.has_edge(src, tgt) or G[src][tgt].get("type") != "references":
                    G.add_edge(
                        src, tgt, type="references", method="regex",
                        evidence=_evidence(content, m.start(), m.end()),
                    )

        # 2) cross_law — 인용된 타 법령명
        for m in RE_CROSS_LAW.finditer(content):
            cited = m.group(1).strip()
            if cited == law_nm:
                continue
            if cited not in G:  # 군 외부 법령 — stub 노드
                if cited not in known_laws:
                    G.add_node(cited, type="law", law_nm=cited, external=True)
                    known_laws.add(cited)
            if not G.has_edge(src, cited):
                G.add_edge(
                    src, cited, type="cross_law", method="regex",
                    evidence=_evidence(content, m.start(), m.end()),
                )

        # 3) byeolpyo — 별표 N (같은 법령 내)
        for m in RE_BYEOLPYO.finditer(content):
            bp_id = article_id(law_nm, f"별표{m.group(1)}")
            if bp_id not in G:
                G.add_node(
                    bp_id, type="article", law_nm=law_nm,
                    article_no=f"별표{m.group(1)}", title=f"별표 {m.group(1)}",
                    content="", domain_tags=["기타"], source_url="",
                )
                G.add_edge(law_nm, bp_id, type="contains", method="structure")
            if not G.has_edge(src, bp_id):
                G.add_edge(
                    src, bp_id, type="byeolpyo", method="regex",
                    evidence=_evidence(content, m.start(), m.end()),
                )

        # 4) delegates — 하위 법령 위임 (법령 단위 엣지)
        for kind, pat in DELEGATE_PATTERNS:
            m = pat.search(content)
            if not m:
                continue
            target_law = _delegate_target(law_nm, kind)
            if target_law and target_law != law_nm and target_law in G:
                if not G.has_edge(law_nm, target_law):
                    G.add_edge(
                        law_nm, target_law, type="delegates", method="regex",
                        evidence=_evidence(content, m.start(), m.end()),
                    )


def _delegate_target(law_nm: str, kind: str) -> str:
    """위임 표현 → 대상 하위 법령명 추정.

    대통령령 → '<법> 시행령', 부령 → '<법> 시행규칙'.
    이미 시행령/시행규칙인 경우는 더 내려갈 곳 없음.
    """
    base = law_nm
    for suffix in (" 시행규칙", " 시행령"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    if kind == "대통령령":
        return f"{base} 시행령"
    return f"{base} 시행규칙"


# ─── 메인 ──────────────────────────────────────────────────────────────────


async def fetch_law(client: LawGoKrClient, law_nm: str) -> tuple[list[dict], str] | None:
    """법령명 정확 일치 검색 → 조문 목록. (articles, source_url) 또는 None."""
    laws = await client.search_law(law_nm, law_type="LAW")
    if not laws:
        print(f"  ✗ 검색 결과 없음: {law_nm}")
        return None
    # 부분일치 주의 — 정확히 일치하는 항목 우선
    target = next((law for law in laws if law["law_nm"] == law_nm), None)
    if target is None:
        print(f"  ⚠ 정확 일치 없음, 첫 결과 사용: {law_nm} → {laws[0]['law_nm']}")
        target = laws[0]
    articles = await client.get_law_articles(target["law_id"], "LAW")
    source_url = f"https://www.law.go.kr/법령/{target['law_nm']}"
    print(f"  ✓ {target['law_nm']} (MST={target['law_id']}) — 조문 {len(articles)}개")
    return articles, source_url


async def build(targets: list[str]) -> None:
    client = LawGoKrClient()
    G = nx.DiGraph()
    known_laws: set[str] = set(targets)

    # 1단계: 모든 법령 fetch + 노드 생성 (엣지 전에 노드가 다 있어야 인용 해소됨)
    fetched: dict[str, list[dict]] = {}
    print(f"[1] 법령 fetch ({len(targets)}개)")
    for law_nm in targets:
        res = await fetch_law(client, law_nm)
        if res is None:
            continue
        articles, source_url = res
        fetched[law_nm] = articles
        add_law_nodes(G, law_nm, articles, source_url)

    # fetch 결과 검증 — 빈/부분 결과로 기존 정상 graph.json 을 덮어쓰지 않도록.
    # (법제처 API 장애·키 문제·IP 제한 시 전부 실패하면 exit 1 → 파일 미작성)
    if not fetched:
        sys.exit(
            f"✗ 빌드 중단: {len(targets)}개 법령 fetch 전부 실패 "
            "(법제처 API 오류 / LAW_API_KEY / IP 제한 의심). "
            "기존 graph.json 을 보존하기 위해 파일을 쓰지 않습니다."
        )
    if len(fetched) < len(targets):
        missing = [t for t in targets if t not in fetched]
        print(f"  ⚠ 경고: {len(missing)}개 법령 fetch 실패 — {missing}")

    # 2단계: 엣지 추출 (노드 모두 등록된 뒤)
    print(f"\n[2] 엣지 추출")
    for law_nm, articles in fetched.items():
        extract_edges(G, law_nm, articles, known_laws)

    await client.close()

    # 3단계: export
    edge_types: dict[str, int] = {}
    for _, _, d in G.edges(data=True):
        edge_types[d.get("type", "?")] = edge_types.get(d.get("type", "?"), 0) + 1

    data = nx.node_link_data(G, edges="links")
    data["meta"] = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "law_count": len(fetched),
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "edge_types": edge_types,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[3] 저장 완료 → {OUT_PATH}")
    print(f"  law={len(fetched)}  node={G.number_of_nodes()}  edge={G.number_of_edges()}")
    print(f"  edge_types={edge_types}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="단일 법령명만 빌드 (품질 확인용)")
    args = ap.parse_args()

    targets = [args.only] if args.only else LAW_GROUP
    asyncio.run(build(targets))


if __name__ == "__main__":
    main()
