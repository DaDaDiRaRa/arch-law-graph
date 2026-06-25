# arch-law-graph — Claude 컨텍스트

건축 법령 관계 그래프 탐색기. 법제처 DRF API → `data/graph.json` → React/Vite SPA.
실무자(건축설계 소장·중간관리자)가 **건축 법령군(19개)을 주제별·피인용 순으로 빠르게 탐색**하는 게 핵심 목적.

---

## 프로젝트 구조

```
builder/          # Python — 법제처 fetch → graph.json 빌드
  build_graph.py  # 11개 법령 전체 빌드. --only 건축법 으로 단일 법령만 가능
  law_go_kr_client.py  # 법제처 DRF API 클라이언트 (별표 포함)
  fetch_test.py   # 빠른 fetch 검증
  requirements.txt

web/src/
  App.jsx            # 최상위 shell — SearchView 하나 감싸는 구조
  views/SearchView.jsx  # 검색-퍼스트 메인 뷰 (케이스노트/빅케이스 벤치마크)
  lib/lawContent.jsx    # 별표 테이블 파서·렌더러, LawBody 컴포넌트
  data.js              # 공유 데이터: internalLaws, articlesByLaw, nodeById,
                       # citeIn, maxCite, outRel, inRel, lawOf(), lawColor(),
                       # familyOf(), tier(), DOMAINS, domainCount, etc.
  App.css              # 노션/토스풍 화이트 테마. --accent: #3182f6

data/graph.json   # 빌드 산출물. git에 추적됨 (배포 시 번들)
.github/
  workflows/refresh.yml         # 매일 07:00 KST 자동 갱신 크론
  scripts/graph_hash.py         # built_at 제외 MD5 해시 — 변경 감지용
Dockerfile        # multistage: node:20-alpine 빌드 → nginx:alpine 서빙
nginx.conf        # port 8080, gzip, /assets/ 1년 캐시, SPA fallback
```

---

## 현재 상태 (2026-06-25 기준)

- **graph.json**: node≈2815, edge≈8761 — 법령 19 + 고시 17 + 서울시 조례 4 + 대법원 판례 40 + 법령해석례 60 (Phase 1–4 완료)
- **배포**: Cloud Run (Method B — GitHub push → 자동 재배포)
- **자동갱신**: 로컬 Windows 작업 스케줄러 "arch-law-graph 자동갱신" (매일 09:00, `scripts/refresh_local.ps1`). GitHub Actions 크론은 비활성화 — 법제처 API가 GH 러너(해외 IP)를 차단해 빈 결과 반환하기 때문.
- **빌드 venv**: `D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe` (networkx·httpx·dotenv 설치)
- **GitHub**: `https://github.com/DaDaDiRaRa/arch-law-graph`

### 법령군 (19개) — `builder/build_graph.py` LAW_GROUP

- 건축법 패밀리: 건축법/시행령/시행규칙 + 피난ㆍ방화구조 규칙·설비기준 규칙·구조기준 규칙·건축물대장 규칙
- 국토계획: 국토계획법/시행령/시행규칙
- 주차장법/시행령/시행규칙
- 건축물의 분양법/시행령/시행규칙
- 녹색건축물 조성 지원법/시행령/시행규칙

### 확장 로드맵 (실무 가치 순)

1. ✅ Phase 1 — 누락 위임 부령·하위법령 보강 (target=law, 완료 2026-06-25)
2. ✅ Phase 2 — 국토부 핵심 건축 고시 17개 (admrul, 완료 2026-06-25). `ADMRUL_GROUP` 참고. 고시 노드는 `category="고시"`. 조문형식 아닌 고시(면적·높이 기준 등)는 장(章) 단위 blob 분할, hwp 첨부만 있는 고시(건축구조기준)는 자동 스킵.
3. ✅ Phase 3 — 서울특별시 건축 조례 4종 (ordin, 완료 2026-06-25). `ORDIN_GROUP` 참고. 조례 노드는 `category="조례"`. 조문번호 6자리(조4+가지2)는 `_ordin_article_no`로 정규화. 다른 지자체 확장 시 ORDIN_GROUP에 (지자체기관명, 자치법규명) 추가.
4. ✅ Phase 4 — 대법원 판례 40 + 법령해석례 60 (prec/expc, 완료 2026-06-25). 각 문서를 law+단일 article('전문') 노드(category="판례"/"해석례")로 모델링. 참조조문·안건명·이유에서 (법령명, 제N조) 추출(`extract_article_refs`) → 실재 조문 노드로 `applied`/`interpreted` 엣지. 판례는 대법원만(비대법원은 본문 XML 미제공). PREC_KEYWORDS/EXPC_KEYWORDS·PREC_CAP/EXPC_CAP로 범위 조절.

### 노드 category 체계

법령(없음)·고시(`고시`)·조례(`조례`)·판례(`판례`)·해석례(`해석례`). data.js 의 lawColor/familyOf 가 색상·라벨 분기. 판례/해석례→조문 엣지(applied/interpreted)는 조문의 '피인용'(citeIn/inRel)에 집계됨.

---

## 핵심 아키텍처 결정

### 데이터 흐름
```
법제처 DRF API → build_graph.py → data/graph.json
                                        ↓ (vite build 시 번들)
                                   nginx 정적 서빙 (Cloud Run)
```
런타임 API 없음. 키 불필요. 순수 정적 SPA.

### UI — 검색-퍼스트 탐색기
케이스노트·빅케이스 벤치마크 기반. 차별점은 **19개 법령 횡단 + 주제(domain) 필터**.

- 검색창 중심 (조문 번호/제목/본문 풀텍스트)
- 검색 문법: `"정확한 구절"`, `-제외어`, AND(스페이스)
- 결과 정렬: 피인용 수 내림차순
- 인용 체인 칩: 같은 법령 패밀리 내비게이션
- 별표 인라인 렌더링 (HTML table, `.bp-box` fallback)
- ★ 북마크 (localStorage)
- 도메인 칩 (건폐율·용적률·높이 등 8카테고리) 2차 필터

### 별표 파싱
법제처 `<별표내용>` XML 태그에 전체 텍스트 있음 (최대 26,561자).
hwp 파일 불필요 — `rhwp-python (GitHub: DaDaMeon)` 은 필요 시 폴백.

East Asian Width-aware 테이블 파서:
- `charW(ch)`: CJK=2, ASCII=1 디스플레이 너비
- `colBoundaries(lines)`: 디스플레이 폭 기준 컬럼 경계 추출
- `parseTable(lines)` → `{header, rows}` | null
- 커버리지: 95% (서식/양식 제외, 순수 별표만)

---

## 현재 사용 중인 API

### 법제처 DRF Open API (핵심)
- Endpoint: `https://www.law.go.kr/DRF/`
- `lawSearch.do?target=law&query={법령명}` — 법령 검색
- `lawService.do?target=law&MST={법령일련번호}` — 법령 조문 + 별표 XML
- 키: `.env`의 `LAW_API_KEY`, GitHub Secret `LAW_API_KEY`

---

## 추가할 수 있는 API (우선순위 순)

### 1. 지자체 조례 (법제처 DRF, `target=ordin`) ← 가장 높은 가치
- **파서가 이미 지원함** (`law_go_kr_client.py`에 `ordin` 분기 존재)
- 건축 조례는 건폐율·용적률·높이 완화 규정이 자치구마다 다름
- 실무자 페인포인트: 어느 조례가 어느 법을 위임받아 완화하는지 한눈에 보이지 않음
- 추가 방법: `build_graph.py`의 `LAW_GROUP`에 조례 법령명 추가 + `target=ordin`으로 fetch
- 주의: 조례는 수천 개 → 서울·부산 등 주요 지자체 건축 조례만 선별 필요

### 2. 판례·해석 연결 (대법원 종합법률정보 API)
- `https://glaw.scourt.go.kr/wsjo/lawjnl/sjo150.do` 계열
- 조문 클릭 시 "이 조문이 적용된 판례 N건" 링크 가능
- 단, 건축 분야 판례는 상대적으로 적고 API 안정성 검토 필요

### 3. 국가공간정보포털 / 건축물 통계 (선택)
- 조문과 직접 연결하기 어려워 우선순위 낮음

---

## 빌드 / 실행

```bash
# Python (자매 앱 venv 재사용 또는 별도)
pip install -r builder/requirements.txt
python builder/build_graph.py           # 전체 11개 법령
python builder/build_graph.py --only 건축법  # 단일 법령 테스트

# Web (개발)
cd web
npm install
npm run dev    # http://localhost:5173

# Web (프로덕션 빌드)
cd web
npm run build  # dist/ 생성

# Docker
docker build -t arch-law-graph .
docker run -p 8080:8080 arch-law-graph
```

**중요**: 항상 프로젝트 루트 `d:\APPS\arch-law-graph`에서 실행. `.env` 위치가 루트.

---

## 환경 변수

```
LAW_API_KEY=...   # 법제처 DRF API 키 (필수)
```
GitHub Actions Secret: `LAW_API_KEY` (Settings → Secrets and variables → Actions).

---

## 자동 갱신 워크플로 (.github/workflows/refresh.yml)

- 스케줄: `0 22 * * *` UTC = 07:00 KST
- 단계: checkout → pip install → 해시 전 → `build_graph.py` → 해시 후 → 변경 시만 커밋·푸시
- `graph_hash.py`: `built_at` 제외 MD5 비교 (타임스탬프만 바뀐 경우 커밋 안 함)
- Node.js 20 deprecation 경고는 비중단(non-breaking) — GitHub 인프라 전환 안내일 뿐

---

## 알려진 이슈 / 픽스 이력

| 이슈 | 픽스 |
|------|------|
| 별표 내용 "hwp 불가" 하드코딩 | `<별표내용>` XML 태그 읽도록 수정 |
| 서식(양식)이 별표로 오파싱 | `별표구분 != "별표"` 인 항목 스킵 |
| 한글 컬럼 경계 오탐 | East Asian Width-aware `charW()` 적용 |
| 빈 줄로 테이블 블록 분리 | 테이블 내부 빈 줄 스킵 로직 추가 |
| delegates 자기참조 루프 | `target_law != law_nm` 가드 추가 |
| Vite fs.allow 오류 | `server: { fs: { allow: ['..'] } }` 추가 |

---

## 다음 작업 후보

1. **조례 확장** — `target=ordin`, 서울시 건축 조례부터
2. **검색 고도화** — 초성 검색, 동의어 (예: "건폐율"↔"건축면적의 비율")
3. **인용 관계 시각화** — 특정 조문 선택 시 인용/피인용 미니 그래프 패널
4. **Node.js 24 경고 제거** — `actions/checkout@v5`, `actions/setup-python@v6` 업데이트
