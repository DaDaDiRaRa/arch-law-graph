"""법제처 국가법령정보 공동활용(DRF) API 클라이언트.

API 문서: https://open.law.go.kr/LSO/openApi/openApiInfo.do
환경변수: LAW_API_KEY  (사이트 표기: OC 인증키)

엔드포인트:
  - 법령/조례 목록: GET /DRF/lawSearch.do
  - 법령/조례 본문: GET /DRF/lawService.do
"""
from __future__ import annotations

import html
import logging
import os
import re
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BASE = "https://www.law.go.kr/DRF"


class LawGoKrClient:
    def __init__(self) -> None:
        self._key = os.getenv("LAW_API_KEY", "")
        if not self._key:
            logger.warning("LAW_API_KEY 미설정 — 법제처 API 조회 불가")
        self._http = httpx.AsyncClient(timeout=20)

    async def close(self) -> None:
        await self._http.aclose()

    # ─── 법령 검색 ────────────────────────────────────────────────────────

    async def search_law(self, keyword: str, law_type: str = "LAW") -> list[dict]:
        """법령 키워드 검색.

        law_type: 'LAW' (법률) | 'CST' (자치법규/조례)
        Returns: [{law_id, law_nm, ef_yd, law_type}, ...]
        """
        if not self._key:
            return []

        target = "ordin" if law_type == "CST" else "law"
        params = {
            "OC": self._key,
            "target": target,
            "type": "JSON",
            "query": keyword,
            "display": 10,
            "page": 1,
        }

        try:
            r = await self._http.get(f"{BASE}/lawSearch.do", params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("법령 검색 오류 (%s): %s", keyword, e)
            return []

        if law_type == "CST":
            items = body.get("OrdinSearch", {}).get("law", []) or []
        else:
            items = body.get("LawSearch", {}).get("law", []) or []

        if isinstance(items, dict):
            items = [items]

        result = []
        for item in items:
            if law_type == "CST":
                law_id = item.get("자치법규일련번호", "")
                law_nm = item.get("자치법규명", "")
                # 상세링크에서 MST 번호 추출 (백업)
                if not law_id:
                    link = item.get("자치법규상세링크", "")
                    m = re.search(r"MST=(\d+)", link)
                    law_id = m.group(1) if m else ""
            else:
                # 법령ID(통합 ID)가 아니라 법령일련번호(MST)를 사용해야 lawService.do 가 동작.
                # 상세링크 fallback 으로 MST 추출하기도 함.
                law_id = item.get("법령일련번호", "")
                if not law_id:
                    link = item.get("법령상세링크", "")
                    m = re.search(r"MST=(\d+)", link)
                    law_id = m.group(1) if m else ""
                law_nm = item.get("법령명한글", "")

            if law_id and law_nm:
                result.append({
                    "law_id": law_id,
                    "law_nm": law_nm,
                    "ef_yd": item.get("시행일자", ""),
                    "law_type": law_type,
                    "org": item.get("지자체기관명", ""),
                })

        return result

    # ─── 법령 본문 조회 ───────────────────────────────────────────────────

    async def get_law_articles(self, law_id: str, law_type: str = "LAW") -> list[dict]:
        """법령 ID(MST)로 전체 조문 목록 반환.

        Returns: [{article_no, title, content}, ...]
        """
        if not self._key or not law_id:
            return []

        target = "ordin" if law_type == "CST" else "law"
        params = {"OC": self._key, "target": target, "MST": law_id, "type": "XML"}
        try:
            r = await self._http.get(f"{BASE}/lawService.do", params=params)
            r.raise_for_status()
            xml_text = r.text
        except Exception as e:
            logger.error("법령 본문 조회 오류 (MST=%s): %s", law_id, e)
            return []

        return _parse_law_xml(xml_text)

    # ─── 행정규칙(고시·지침·예규) ─────────────────────────────────────────

    async def search_admrul(self, name: str) -> dict | None:
        """행정규칙명 정확 일치 + 현행 항목 검색. Returns {adm_id, name, kind, org} | None.

        adm_id 는 lawService.do 의 ID= 파라미터로 쓰이는 행정규칙일련번호.
        """
        if not self._key:
            return None
        for page in (1, 2):
            params = {
                "OC": self._key, "target": "admrul", "type": "JSON",
                "query": name, "display": 50, "page": page,
            }
            try:
                r = await self._http.get(f"{BASE}/lawSearch.do", params=params)
                r.raise_for_status()
                body = r.json()
            except Exception as e:
                logger.error("행정규칙 검색 오류 (%s): %s", name, e)
                return None
            items = body.get("AdmRulSearch", {}).get("admrul", []) or []
            if isinstance(items, dict):
                items = [items]
            if not items:
                break
            for it in items:
                if (it.get("행정규칙명") or "").strip() != name:
                    continue
                if (it.get("현행연혁구분") or "").strip() not in ("", "현행"):
                    continue
                adm_id = (it.get("행정규칙일련번호") or "").strip()
                if not adm_id:
                    m = re.search(r"ID=(\d+)", it.get("행정규칙상세링크", ""))
                    adm_id = m.group(1) if m else ""
                if adm_id:
                    return {
                        "adm_id": adm_id,
                        "name": name,
                        "kind": (it.get("행정규칙종류") or "").strip(),
                        "org": (it.get("소관부처명") or "").strip(),
                    }
        return None

    async def get_admrul_articles(self, adm_id: str) -> list[dict]:
        """행정규칙 일련번호(ID)로 조문(<조문내용>) + 별표 목록 반환."""
        if not self._key or not adm_id:
            return []
        params = {"OC": self._key, "target": "admrul", "ID": adm_id, "type": "XML"}
        try:
            r = await self._http.get(f"{BASE}/lawService.do", params=params)
            r.raise_for_status()
            xml_text = r.text
        except Exception as e:
            logger.error("행정규칙 본문 조회 오류 (ID=%s): %s", adm_id, e)
            return []
        return _parse_admrul_xml(xml_text)

    # ─── 자치법규(조례) 정확 매칭 ─────────────────────────────────────────

    async def search_ordin(self, name: str, org: str) -> dict | None:
        """자치법규명 + 지자체기관명 정확 일치 검색. {ordin_id, name, org} | None.

        ordin_id 는 lawService.do 의 MST 파라미터로 쓰이는 자치법규일련번호.
        """
        if not self._key:
            return None
        for page in (1, 2, 3, 4):
            params = {
                "OC": self._key, "target": "ordin", "type": "JSON",
                "query": name, "display": 100, "page": page,
            }
            try:
                r = await self._http.get(f"{BASE}/lawSearch.do", params=params)
                r.raise_for_status()
                body = r.json()
            except Exception as e:
                logger.error("조례 검색 오류 (%s): %s", name, e)
                return None
            items = body.get("OrdinSearch", {}).get("law", []) or []
            if isinstance(items, dict):
                items = [items]
            if not items:
                break
            for it in items:
                if (it.get("자치법규명") or "").strip() != name:
                    continue
                if (it.get("지자체기관명") or "").strip() != org:
                    continue
                ordin_id = (it.get("자치법규일련번호") or "").strip()
                if not ordin_id:
                    m = re.search(r"MST=(\d+)", it.get("자치법규상세링크", ""))
                    ordin_id = m.group(1) if m else ""
                if ordin_id:
                    return {"ordin_id": ordin_id, "name": name, "org": org}
        return None

    # ─── org 필터 검색 (시도 직제 조례 우선) ────────────────────────────

    async def _search_with_org_filter(
        self, keyword: str, org_name: str, law_type: str = "CST",
        law_nm_keyword: str = "",
    ) -> list[dict]:
        """최대 3페이지 검색해 org_name + 조례명 키워드가 일치하는 조례를 반환.

        law_nm_keyword: 조례명에 반드시 포함되어야 할 핵심어 (예: '도시계획')
        정확 일치가 없으면 page 1의 첫 번째 결과를 반환.
        """
        fallback: list[dict] = []
        target = "ordin" if law_type == "CST" else "law"
        # 조례명 필터: 공백 제거 버전으로 비교 (예: '도시계획 조례' → '도시계획')
        nm_filter = law_nm_keyword.replace(" ", "") if law_nm_keyword else ""

        for page in range(1, 4):
            params = {
                "OC": self._key,
                "target": target,
                "type": "JSON",
                "query": keyword,
                "display": 10,
                "page": page,
            }
            try:
                r = await self._http.get(f"{BASE}/lawSearch.do", params=params)
                r.raise_for_status()
                body = r.json()
            except Exception as e:
                logger.error("법령 검색(page=%s) 오류: %s", page, e)
                break

            raw = body.get("OrdinSearch", {}).get("law", []) or []
            if isinstance(raw, dict):
                raw = [raw]
            if not raw:
                break

            for item in raw:
                law_id = item.get("자치법규일련번호", "")
                law_nm = item.get("자치법규명", "")
                if not law_id:
                    m = re.search(r"MST=(\d+)", item.get("자치법규상세링크", ""))
                    law_id = m.group(1) if m else ""
                org = item.get("지자체기관명", "")
                entry = {
                    "law_id": law_id,
                    "law_nm": law_nm,
                    "ef_yd": item.get("시행일자", ""),
                    "law_type": law_type,
                    "org": org,
                }
                nm_match = (nm_filter in law_nm.replace(" ", "")) if nm_filter else True
                if law_id and law_nm and org == org_name and nm_match:
                    logger.debug("org+조례명 정확 매칭: %s (%s)", law_nm, org)
                    return [entry]
                if page == 1 and law_id and law_nm and not fallback:
                    fallback = [entry]

        return fallback

    # ─── 조례 빠른 조회 (지역명 + 법령유형) ─────────────────────────────

    async def fetch_ordinance(
        self, region_name: str, law_keyword: str
    ) -> list[dict]:
        """예: region_name='서울특별시', law_keyword='도시계획 조례' → 조문 목록.

        지자체기관명이 region_name과 정확히 일치하는 조례를 우선 선택.
        page 1~3까지 검색해 정확 일치를 찾은 뒤 없으면 첫 번째 결과 사용.
        """
        query = f"{region_name} {law_keyword}"
        # 공백 제거한 전체 키워드를 조례명 필터로 사용 (예: '도시계획 조례' → '도시계획조례')
        nm_key = law_keyword.replace(" ", "") if law_keyword else ""
        laws = await self._search_with_org_filter(
            query, region_name, law_type="CST", law_nm_keyword=nm_key
        )
        if not laws:
            laws = await self.search_law(law_keyword, law_type="LAW")
        if not laws:
            logger.warning("법령 검색 결과 없음: %s", query)
            return []

        law = laws[0]
        articles = await self.get_law_articles(law["law_id"], law["law_type"])
        for art in articles:
            art["law_nm"] = law["law_nm"]
            art["law_id"] = law["law_id"]
            art["source_url"] = f"https://www.law.go.kr/법령/{law['law_nm']}"
        return articles


# ─── XML 파싱 ─────────────────────────────────────────────────────────────


def _parse_law_units(units: list) -> list[dict]:
    """법률(target=law) <조문단위> 목록 파싱.

    조문여부=='조문' 만 실제 조문. '전문' 은 장/절 구분자라 제외.
    본문 = 조문내용 + 모든 항/호/목 내용 (인용 추출용 전체 텍스트).
    """
    articles: list[dict] = []
    for unit in units:
        if (unit.findtext("조문여부") or "").strip() != "조문":
            continue

        no = (unit.findtext("조문번호") or "").strip()
        branch = (unit.findtext("조문가지번호") or "").strip()
        article_no = f"{no}의{branch}" if branch else no
        title = (unit.findtext("조문제목") or "").strip()
        ef_yd = (unit.findtext("조문시행일자") or "").strip()

        parts: list[str] = []
        head = (unit.findtext("조문내용") or "").strip()
        if head:
            parts.append(head)
        for hang in unit.iter("항"):
            hc = (hang.findtext("항내용") or "").strip()
            if hc:
                parts.append(hc)
        for ho in unit.iter("호"):
            hoc = (ho.findtext("호내용") or "").strip()
            if hoc:
                parts.append(hoc)
        for mok in unit.iter("목"):
            mc = (mok.findtext("목내용") or "").strip()
            if mc:
                parts.append(mc)
        content = "\n".join(parts)

        if content:
            articles.append({
                "article_no": article_no,
                "title": title,
                "content": content,
                "ef_yd": ef_yd,
            })
    return articles


def _ordin_article_no(no_raw: str) -> str:
    """조례 조문번호 6자리(조4+가지2) → '1', '10의2' 등으로 변환.

    예: '000100' → '1', '001002' → '10의2'. 비표준이면 원본 유지.
    """
    no_raw = no_raw.strip()
    if no_raw.isdigit() and len(no_raw) == 6:
        jo, ga = int(no_raw[:4]), int(no_raw[4:])
        return f"{jo}의{ga}" if ga else str(jo)
    return no_raw


def _parse_ordin_jo(root) -> list[dict]:
    """자치법규(target=ordin) <조> 목록 파싱. 조문여부 Y 만.

    조문번호는 6자리(조4+가지2) 포맷이라 _ordin_article_no 로 정규화.
    """
    articles: list[dict] = []
    for jo in root.iter("조"):
        if (jo.findtext("조문여부") or "").strip() != "Y":
            continue
        content_text = (jo.findtext("조내용") or "").strip()
        if content_text:
            articles.append({
                "article_no": _ordin_article_no(jo.findtext("조문번호") or ""),
                "title": (jo.findtext("조제목") or "").strip(),
                "content": content_text,
            })
    return articles


def _parse_byeolpyo_units(root) -> list[dict]:
    """<별표단위> 목록 파싱 (법령·행정규칙 공용).

    별표 본문 텍스트는 <별표내용> 에 인라인 제공(표는 선문자). 삭제/빈 서식 제외.
    """
    out: list[dict] = []
    for byp in root.iter("별표단위"):
        bp_title = html.unescape((byp.findtext("별표제목") or "").strip())
        bp_content = html.unescape((byp.findtext("별표내용") or "").strip())
        if not bp_title or bp_title.startswith("삭제") or len(bp_content) < 30:
            continue  # 폐지된 빈 서식 등 본문 없는 항목 스킵

        no_raw = (byp.findtext("별표번호") or "").strip()
        br_raw = (byp.findtext("별표가지번호") or "").strip()
        try:
            no = str(int(no_raw))  # "0001" → "1"
        except ValueError:
            no = no_raw
        try:
            branch = int(br_raw)
        except ValueError:
            branch = 0
        gubun = (byp.findtext("별표구분") or "별표").strip()
        if gubun != "별표":
            continue  # 서식(신청서 양식)은 표가 아니라 제외

        article_no = f"별표{no}" + (f"의{branch}" if branch else "")
        out.append({"article_no": article_no, "title": bp_title, "content": bp_content})
    return out


# 행정규칙 <조문내용> 머리: "제1조(목적) …", "제3조의2(…) …"
RE_ADMRUL_JO = re.compile(r"^제\s*(\d+)\s*조(?:의\s*(\d+))?\s*(?:\(([^)]*)\))?")
# 조문형식이 아닌 고시의 장 헤더: "제1장 총칙", "제2장 건축물의 면적 산정기준"
RE_ADMRUL_JANG = re.compile(r"(?m)^\s*(제\s*\d+\s*장[^\n]*)$")


def _chunk_admrul_blob(blob: str) -> list[dict]:
    """조문(제N조) 형식이 아닌 고시 본문(blob)을 장(章) 단위로 분할.

    "건축물 면적, 높이 등 세부 산정기준"처럼 제N장 / 2.1.1 번호 체계인 경우.
    본문이 hwp 첨부 안내문뿐이면(짧거나 "버튼을 이용") 빈 목록 → 호출부에서 스킵.
    """
    blob = re.sub(r"<img\b[^>]*>", " ", blob).replace("</img>", " ")
    stripped = blob.strip()
    if len(stripped) < 80 or "버튼을 이용" in stripped:
        return []  # 본문 없음(첨부 안내문)

    matches = list(RE_ADMRUL_JANG.finditer(blob))
    if not matches:
        return [{"article_no": "전문", "title": "전문", "content": stripped}]

    arts: list[dict] = []
    for i, mt in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
        header = mt.group(1).strip()
        jno = re.search(r"제\s*(\d+)\s*장", header).group(1)
        content = blob[mt.start():end].strip()
        if len(content) > 20:
            arts.append({"article_no": f"제{jno}장", "title": header, "content": content})
    return arts


def _parse_admrul_xml(xml_text: str) -> list[dict]:
    """행정규칙(target=admrul) XML 파싱 — 확인됨 2026-06-25.

    구조: root=<AdmRulService>. 본문은 <조문단위>가 아니라 root 직속
    <조문내용> 요소가 조마다 1개씩("제N조(제목) …"). 별표는 법령과 동일한 <별표단위>.
    조문(제N조) 형식이 아닌 고시(제N장/2.1.1 번호)는 _chunk_admrul_blob 로 장 분할.
    본문이 hwp 첨부뿐인 고시는 빈 목록 반환 → 호출부에서 스킵.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("행정규칙 XML 파싱 오류: %s", e)
        return []

    articles: list[dict] = []
    blob_parts: list[str] = []
    for jo in root.findall("조문내용"):
        text = html.unescape((jo.text or "").strip())
        if not text:
            continue
        m = RE_ADMRUL_JO.match(text)
        if m:
            no, branch, title = m.group(1), m.group(2), (m.group(3) or "").strip()
            article_no = f"{no}의{branch}" if branch else no
            articles.append({"article_no": article_no, "title": title, "content": text})
        else:
            blob_parts.append(text)  # 장 헤더·비조문 형식 본문

    # 제N조 형식이 하나도 없으면 blob(제N장/항목 번호) 체계로 보고 장 분할
    if not articles and blob_parts:
        articles = _chunk_admrul_blob("\n".join(blob_parts))

    articles.extend(_parse_byeolpyo_units(root))
    return articles


def _parse_law_xml(xml_text: str) -> list[dict]:
    """DRF 법령/자치법규 XML 조문 파싱 (두 스키마 자동 분기).

    ── 법률 (target=law, root=<법령>) — 확인됨 2026-06-23 ──
      <조문단위>: 조문번호·조문여부('조문'/'전문')·조문가지번호·조문제목·
                  조문시행일자·조문내용 + <항>/<호>/<목>
    ── 자치법규 (target=ordin, root=<LawService>) — 확인됨 2026-05-15 ──
      <조>: 조문번호·조문여부(Y/N)·조제목·조내용(항·호 인라인)

    별표는 본문이 hwp 첨부라 비어있지만 제목·URL 은 신호로 보존.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("법령 XML 파싱 오류: %s", e)
        return []

    units = root.findall(".//조문단위")
    if units:
        articles = _parse_law_units(units)
    else:
        articles = _parse_ordin_jo(root)

    articles.extend(_parse_byeolpyo_units(root))

    # 폴백 — 파싱 0건일 때 전체 XML 통째 (예전 스키마 또는 응답 이상 대응)
    if not articles and xml_text.strip():
        try:
            articles = [{
                "article_no": "",
                "title": "전문",
                "content": ET.tostring(root, encoding="unicode"),
            }]
        except Exception:
            pass

    return articles
