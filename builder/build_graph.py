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
    # ── Stage 11: 심의 별도 법령 5종 — 건축 인허가 연관 평가·협의 ──
    # 교통영향분석·환경영향평가·경관심의·지하안전평가·재해영향평가 근거 조문 chip 용.
    "도시교통정비촉진법", "도시교통정비촉진법 시행령",
    "환경영향평가법", "환경영향평가법 시행령",
    "경관법", "경관법 시행령",
    "지하안전관리에 관한 특별법", "지하안전관리에 관한 특별법 시행령",
    "자연재해대책법", "자연재해대책법 시행령",
]

# ─── 대상 행정규칙(고시·지침·예규) ─────────────────────────────────────────
# 국토부 소관 설계 실무 직결 고시. 정확명 일치 + 현행만 fetch.
# 본문이 hwp 첨부뿐인 고시(예: 건축구조기준)는 텍스트가 없어 자동 스킵됨.
ADMRUL_GROUP = [
    "건축물 면적, 높이 등 세부 산정기준",          # 건폐율·용적률·높이 산정
    "건축물의 에너지절약설계기준",                  # 단열·열관류율(별표)
    "건축물 안전영향평가 세부기준",
    "건축물의 화재안전성능보강 방법 등에 관한 기준",
    "건축자재등 품질인정 및 관리기준",              # 방화문·마감재 난연성능 통합
    "건축물 해체계획서의 작성 및 감리업무 등에 관한 기준",
    "건축물관리계획 작성기준",
    "건축물의 설계도서 작성기준",
    "공동주택 결로 방지를 위한 설계기준",
    "범죄예방 건축기준 고시",                        # CPTED
    "실내건축의 구조·시공방법 등에 관한 기준",
    "녹색건축 인증 기준",
    "제로에너지건축물 인증 기준",
    "지능형건축물 인증기준",
    "특수구조 건축물 대상기준",
    "에너지절약형 친환경주택의 건설기준",
    "기존 건축물의 에너지성능 개선기준",
    "건축구조기준",                                  # hwp 첨부 — 스킵될 수 있음
]

# ─── 대상 자치법규(조례) ───────────────────────────────────────────────────
# (지자체기관명, 자치법규명) 정확 매칭. 서울특별시 본청부터 (자치구 아님).
# 7개 광역시(서울·부산·인천·대구·대전·광주·울산) + 세종·제주 + 특례시(수원·용인·고양·창원) + 경기도
# + 인구 50만↑ 일반시(성남·청주·전주·천안) = 카드 17개 지자체(+경기도는 검색용만).
# ─── 전국 시(市) 조례 목록 — builder/ordin_group.py (inventory_ordin.py 자동생성) ───
# 갱신: python builder/inventory_ordin.py 재실행 → ordin_group.py 재생성.
from ordin_group import ORDIN_GROUP  # noqa: E402

# ─── 판례·해석례 수집 키워드/상한 ──────────────────────────────────────────
# 카드 4영역(완화·심의·친환경·가로구역) + 도시계획 확장 토픽 보강(Stage E-10, 2026-06-30).
# 기존 키워드는 순서 보존(현 corpus 안정) + 신규를 뒤에 append → 상향된 cap 슬롯이 신규로 채워짐.
_CARD_TOPIC_KEYWORDS = [
    # 완화·혜택
    "공개공지", "공공기여", "기부채납", "용적률 완화", "임대주택",
    # 심의
    "건축위원회", "교통영향평가", "환경영향평가", "경관", "지하안전", "재해영향평가",
    # 친환경
    "제로에너지건축물", "에너지절약",
    # 가로구역·높이
    "가로구역", "고도지구",
    # 도시계획 확장
    "지구단위계획", "기반시설", "재건축", "재개발", "정비사업",
]
PREC_KEYWORDS = ["건축법", "건폐율", "용적률", "건축물 높이", "일조", "주차장법", "용도지역",
                 "이격거리", "대지경계", "용도변경", "건축허가", "건축신고", "위반건축물",
                 "가설건축물", "국토계획법", "건축물 대수선", "도로 사선", "조경",
                 # 상호 보완(EXPC엔 있고 PREC엔 없던 것)
                 "부설주차장", "녹색건축물",
                 *_CARD_TOPIC_KEYWORDS]
EXPC_KEYWORDS = ["건축법", "건폐율", "용적률", "건축물 높이", "주차장법", "용도지역", "녹색건축물",
                 "이격거리", "대지경계", "용도변경", "건축허가", "건축신고", "위반건축물",
                 "가설건축물", "국토계획법", "건축물 대수선", "부설주차장", "조경",
                 # 상호 보완(PREC엔 있고 EXPC엔 없던 것)
                 "일조", "도로 사선",
                 # 실무 상황어 추가 (diag_expc.py 검증 기여분)
                 "이행강제금", "장애인 편의시설", "방화구획", "바닥면적 산정", "연면적 산정",
                 *_CARD_TOPIC_KEYWORDS]
PREC_CAP = 160   # 대법원 판례 상한 (Stage E-10: 100→160)
EXPC_CAP = 1100  # 법령해석례 상한 (E-11: 240→1100. diag 실측 가용 1077건+여유)


def _ref_pattern(law_names: list[str]) -> re.Pattern:
    """법령명(긴 것 우선) 또는 '제N조[의M]' 매칭 패턴."""
    alt = "|".join(re.escape(n) for n in sorted(set(law_names), key=len, reverse=True))
    return re.compile(f"(?P<law>{alt})|제\\s*(?P<no>\\d+)\\s*조(?:의\\s*(?P<br>\\d+))?")


def extract_article_refs(text: str, pat: re.Pattern) -> list[tuple[str, str]]:
    """본문/참조조문에서 (법령명, 조문번호) 추출.

    직전 등장 법령명에 후속 '제N조'를 귀속 (예: '건축법 제19조, 제20조' → 둘 다 건축법).
    """
    refs: list[tuple[str, str]] = []
    cur: str | None = None
    for m in pat.finditer(text):
        if m.group("law"):
            cur = m.group("law")
        elif cur:
            no, br = m.group("no"), m.group("br")
            refs.append((cur, f"{no}의{br}" if br else no))
    return refs

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
    """조문 노드 ID. 숫자(제N조/제N조의M)만 '제..조'로 감싸고,
    별표·제N장·전문 등 비숫자 번호는 그대로 사용."""
    if re.fullmatch(r"\d+(?:의\d+)?", article_no):
        return f"{law_nm}/제{article_no}조"
    return f"{law_nm}/{article_no}"


def add_law_nodes(
    G: nx.DiGraph, law_nm: str, articles: list[dict], source_url: str,
    category: str | None = None,
) -> None:
    """law 노드 1개 + 소속 article 노드 + contains 엣지.

    category: '고시' 등 — 법령(None)과 행정규칙 구분용(UI 색상·라벨).
    """
    G.add_node(law_nm, type="law", law_nm=law_nm, **({"category": category} if category else {}))
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


def add_doc_node(
    G: nx.DiGraph, node_id: str, title: str, content: str, source_url: str,
    category: str, refs: list[tuple[str, str]], edge_type: str,
    existing_articles: set[str],
) -> int:
    """판례/해석례 = law 노드 1개 + 단일 article('전문') + 참조 조문으로의 엣지.

    refs 중 그래프에 실재하는 조문 노드로만 edge_type 엣지를 연결. 연결 수 반환.
    """
    G.add_node(node_id, type="law", law_nm=node_id, category=category)
    aid = f"{node_id}/전문"
    G.add_node(
        aid, type="article", law_nm=node_id, article_no="전문",
        title=title, content=content, ef_yd="",
        domain_tags=classify_domain(f"{title}\n{content}"), source_url=source_url,
    )
    G.add_edge(node_id, aid, type="contains", method="structure")

    linked = 0
    seen: set[str] = set()
    for law, art in refs:
        tgt = article_id(law, art)
        if tgt in existing_articles and tgt not in seen:
            seen.add(tgt)
            G.add_edge(aid, tgt, type=edge_type, method="ref")
            linked += 1
    return linked


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


async def fetch_admrul(
    client: LawGoKrClient, name: str
) -> tuple[list[dict], str, dict] | None:
    """행정규칙명 정확 일치(현행) 검색 → 조문 목록. (articles, source_url, info) 또는 None.

    본문이 hwp 첨부뿐이라 조문 텍스트가 0건이면 None(스킵).
    """
    info = await client.search_admrul(name)
    if not info:
        print(f"  ✗ 행정규칙 검색 결과 없음: {name}")
        return None
    articles = await client.get_admrul_articles(info["adm_id"])
    if not articles:
        print(f"  ⚠ 본문 텍스트 없음(hwp 첨부 추정) — 스킵: {name}")
        return None
    source_url = f"https://www.law.go.kr/행정규칙/{name}"
    print(f"  ✓ [{info['kind']}] {name} (ID={info['adm_id']}) — 조문 {len(articles)}개")
    return articles, source_url, info


async def fetch_ordin(
    client: LawGoKrClient, org: str, name: str
) -> tuple[list[dict], str] | None:
    """자치법규명+지자체 정확 일치 검색 → 조문 목록. (articles, source_url) 또는 None."""
    info = await client.search_ordin(name, org)
    if not info:
        print(f"  ✗ 조례 검색 결과 없음: {org} | {name}")
        return None
    articles = await client.get_law_articles(info["ordin_id"], "CST")
    if not articles:
        print(f"  ⚠ 본문 없음 — 스킵: {name}")
        return None
    source_url = f"https://www.law.go.kr/자치법규/{name}"
    print(f"  ✓ {name} (MST={info['ordin_id']}) — 조문 {len(articles)}개")
    return articles, source_url


async def build(targets: list[str], include_admrul: bool = True) -> None:
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

    # 1.5단계: 행정규칙(고시) fetch + 노드 생성 (엣지 전, 법령 노드 뒤)
    fetched_admrul: dict[str, list[dict]] = {}
    if include_admrul:
        print(f"\n[1.5] 행정규칙(고시) fetch ({len(ADMRUL_GROUP)}개)")
        for name in ADMRUL_GROUP:
            res = await fetch_admrul(client, name)
            if res is None:
                continue
            articles, source_url, _info = res
            fetched_admrul[name] = articles
            known_laws.add(name)
            add_law_nodes(G, name, articles, source_url, category="고시")

    # 1.6단계: 자치법규(조례) fetch + 노드 생성
    fetched_ordin: dict[str, list[dict]] = {}
    if include_admrul:
        print(f"\n[1.6] 자치법규(조례) fetch ({len(ORDIN_GROUP)}개)")
        for org, name in ORDIN_GROUP:
            res = await fetch_ordin(client, org, name)
            if res is None:
                continue
            articles, source_url = res
            fetched_ordin[name] = articles
            known_laws.add(name)
            add_law_nodes(G, name, articles, source_url, category="조례")

    # 2단계: 엣지 추출 (노드 모두 등록된 뒤) — 법령 + 행정규칙 + 조례
    print(f"\n[2] 엣지 추출")
    for law_nm, articles in {**fetched, **fetched_admrul, **fetched_ordin}.items():
        extract_edges(G, law_nm, articles, known_laws)

    # 2.5단계: 판례(대법원)·법령해석례 — 조문 단위로 연결
    prec_count = expc_count = prec_links = expc_links = 0
    if include_admrul:
        existing_articles = {n for n, d in G.nodes(data=True) if d.get("type") == "article"}
        law_names = [n for n, d in G.nodes(data=True)
                     if d.get("type") == "law" and not d.get("external")]
        pat = _ref_pattern(law_names)

        # 판례 — 대법원만(본문 XML 제공). 키워드 합집합 → 상한.
        print(f"\n[2.5] 판례(대법원) fetch")
        prec_idx: dict[str, dict] = {}
        for kw in PREC_KEYWORDS:
            for it in await client.search_prec(kw, court="대법원"):
                prec_idx.setdefault(it["prec_id"], it)
        for pid in list(prec_idx)[:PREC_CAP]:
            doc = await client.get_prec(pid)
            if not doc:
                continue
            title = doc["사건명"] or doc["사건번호"]
            content = "\n\n".join(filter(None, [
                f"【판시사항】\n{doc['판시사항']}" if doc["판시사항"] else "",
                f"【판결요지】\n{doc['판결요지']}" if doc["판결요지"] else "",
                f"【참조조문】\n{doc['참조조문']}" if doc["참조조문"] else "",
            ])) or doc["판례내용"][:1500]
            refs = extract_article_refs(doc["참조조문"] + "\n" + doc["판시사항"], pat)
            node_id = f"판례 {doc['사건번호']}"
            url = f"https://www.law.go.kr/LSW/precInfoP.do?precSeq={pid}"
            prec_links += add_doc_node(G, node_id, title, content, url,
                                       "판례", refs, "applied", existing_articles)
            prec_count += 1
        print(f"  ✓ 판례 {prec_count}건, 조문 연결 {prec_links}건")

        # 법령해석례
        print(f"\n[2.6] 법령해석례 fetch")
        expc_idx: dict[str, dict] = {}
        for kw in EXPC_KEYWORDS:
            for it in await client.search_expc(kw):
                expc_idx.setdefault(it["expc_id"], it)
        for eid in list(expc_idx)[:EXPC_CAP]:
            doc = await client.get_expc(eid)
            if not doc:
                continue
            title = doc["안건명"] or doc["안건번호"]
            content = "\n\n".join(filter(None, [
                f"【질의요지】\n{doc['질의요지']}" if doc["질의요지"] else "",
                f"【회답】\n{doc['회답']}" if doc["회답"] else "",
                f"【이유】\n{doc['이유'][:4000]}" if doc["이유"] else "",
            ]))
            refs = extract_article_refs(doc["안건명"] + "\n" + doc["이유"], pat)
            node_id = f"해석례 {doc['안건번호']}" if doc["안건번호"] else f"해석례 {eid}"
            url = f"https://www.law.go.kr/LSW/expcInfoP.do?expcSeq={eid}"
            expc_links += add_doc_node(G, node_id, title, content, url,
                                       "해석례", refs, "interpreted", existing_articles)
            expc_count += 1
        print(f"  ✓ 해석례 {expc_count}건, 조문 연결 {expc_links}건")

    await client.close()

    # 3단계: export
    edge_types: dict[str, int] = {}
    for _, _, d in G.edges(data=True):
        edge_types[d.get("type", "?")] = edge_types.get(d.get("type", "?"), 0) + 1

    data = nx.node_link_data(G, edges="links")
    data["meta"] = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "law_count": len(fetched),
        "admrul_count": len(fetched_admrul),
        "ordin_count": len(fetched_ordin),
        "prec_count": prec_count,
        "expc_count": expc_count,
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "edge_types": edge_types,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[3] 저장 완료 → {OUT_PATH}")
    print(f"  law={len(fetched)}  고시={len(fetched_admrul)}  조례={len(fetched_ordin)}  "
          f"판례={prec_count}  해석례={expc_count}  "
          f"node={G.number_of_nodes()}  edge={G.number_of_edges()}")
    print(f"  edge_types={edge_types}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="단일 법령명만 빌드 (품질 확인용)")
    args = ap.parse_args()

    targets = [args.only] if args.only else LAW_GROUP
    # --only(단일 법령 품질확인)일 땐 고시 fetch 생략
    asyncio.run(build(targets, include_admrul=not args.only))


if __name__ == "__main__":
    main()
