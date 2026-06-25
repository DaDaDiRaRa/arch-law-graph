# arch-law-graph — Claude 컨텍스트

건축 법령 관계 그래프 탐색기. 법제처 DRF API → `data/graph.json` → React/Vite SPA.
실무자(건축설계 소장·중간관리자)가 **건축 법령군(19개)을 주제별·피인용 순으로 빠르게 탐색**하는 게 핵심 목적.

---

## 프로젝트 구조

```text
builder/          # Python — 법제처 fetch → graph.json 빌드
  build_graph.py  # 법령 19 + 고시 + 조례 + 판례 + 해석례 전체 빌드. --only 건축법 으로 단일 법령만 가능
  law_go_kr_client.py  # 법제처 DRF 클라이언트 (law/admrul/ordin/prec/expc, 별표 포함)
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

scripts/
  refresh_local.ps1   # 로컬 자동갱신 (작업 스케줄러용): 빌드 → 변경 시 commit·push
data/graph.json   # 빌드 산출물. git에 추적됨 (배포 시 번들)
.github/
  workflows/refresh.yml         # GH Actions 크론 — 비활성화됨(법제처 IP 차단). 수동 dispatch만.
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

```text
법제처 DRF API → build_graph.py → data/graph.json
                                        ↓ (vite build 시 번들)
                                   nginx 정적 서빙 (Cloud Run)
```

런타임 API 없음. 키 불필요. 순수 정적 SPA.

### UI — 검색-퍼스트 탐색기

케이스노트·빅케이스 벤치마크 기반. 차별점은 **법령군 횡단(법률→고시→조례→판례·해석례) + 주제(domain) 필터**.

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
법령·고시·조례 공통으로 `_parse_byeolpyo_units()` 헬퍼가 처리.

East Asian Width-aware 테이블 파서:
- `charW(ch)`: CJK=2, ASCII=1 디스플레이 너비
- `colBoundaries(lines)`: 디스플레이 폭 기준 컬럼 경계 추출
- `parseTable(lines)` → `{header, rows}` | null
- 커버리지: 95% (서식/양식 제외, 순수 별표만)

---

## 현재 사용 중인 API

### 법제처 DRF Open API — 단일 `LAW_API_KEY`로 5개 target 사용

- Endpoint: `https://www.law.go.kr/DRF/` (`lawSearch.do` 검색 + `lawService.do` 본문)
- `target=law` — 법령. 본문은 `MST=` 파라미터.
- `target=admrul` — 행정규칙/고시. 본문은 **`ID=` 파라미터(MST 아님)**. 조문형식 아닌 고시는 장 blob, hwp 첨부뿐이면 본문 없음.
- `target=ordin` — 자치법규/조례. 조문번호 6자리(조4+가지2) 정규화 필요(`_ordin_article_no`).
- `target=prec` — 판례. **대법원만 본문 XML 제공**(비대법원은 빈 응답). 구조화 `참조조문` 필드.
- `target=expc` — 법령해석례. 구조화 필드(안건명/질의요지/회답/이유).
- 키: `.env`의 `LAW_API_KEY`. (런타임 호출 없음 — 빌드 시에만 사용.)
- ⚠ 법제처가 **GitHub Actions 등 해외 데이터센터 IP를 차단** → 빌드는 국내 IP(로컬)에서 수행.

---

## 추가할 수 있는 API (우선순위 순)

### 1. 조례 지자체 확장 (`target=ordin`)

- 현재 서울특별시 본청 4종만 — 부산·인천 등 주요 지자체로 확장 가능.
- `build_graph.py`의 `ORDIN_GROUP`에 (지자체기관명, 자치법규명) 추가.

### 2. 판례·해석례 범위 확대 (`prec`/`expc`)

- 현재 상한 PREC_CAP=40, EXPC_CAP=60. 키워드/상한 조정으로 확대 가능.

### 3. 국가공간정보포털 / 건축물 통계 (선택)

- 조문과 직접 연결하기 어려워 우선순위 낮음. 별도 키(data.go.kr) 필요.

---

## 빌드 / 실행

```bash
# Python — 자매앱 venv 사용 (networkx·httpx·dotenv 설치됨).
#   D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe
# (Windows Store stub 'python'/'py'에는 의존성 없음 — 위 venv 직접 호출)
pip install -r builder/requirements.txt   # 새 venv 구성 시
python builder/build_graph.py           # 전체 빌드(법령+고시+조례+판례+해석례)
python builder/build_graph.py --only 건축법  # 단일 법령 테스트(고시·조례·판례 생략)

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

```text
LAW_API_KEY=...   # 법제처 DRF API 키 (필수, 빌드 시에만 사용)
```

---

## 자동 갱신 (로컬 작업 스케줄러)

GitHub Actions 크론은 **비활성화** — 법제처 API가 GH 러너(해외 IP)를 차단해 빈 결과를 반환하기 때문. 정상 동작하는 로컬 IP에서 수행한다.

- **작업**: Windows 작업 스케줄러 "arch-law-graph 자동갱신", 매일 09:00 (`StartWhenAvailable` — 그 시각 PC 꺼져 있었으면 다음 부팅·로그인 직후 실행).
- **스크립트**: `scripts/refresh_local.ps1` — 해시 전 → `build_graph.py` → 해시 후 → 변경 시만 commit·push(→ Cloud Run 재배포). 변경 없으면 graph.json 원복(트리 청결).
- **안전장치**: 빌드가 빈 결과(법령 fetch 전부 실패)면 `build_graph.py`가 exit 1 → 파일 미작성·커밋 안 함. refresh.yml에도 node_count==0 가드 잔존.
- `graph_hash.py`: `built_at` 제외 MD5 비교 (타임스탬프만 바뀐 경우 커밋 안 함).
- 로그: `scripts/refresh_local.log` (gitignore됨).

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
| 자동갱신이 빈 graph.json 커밋 → 배포 0건 | 정상본 복구 + `build_graph.py` exit 1(빈 결과 시) + workflow node_count 가드 |
| 법제처 API가 GH Actions IP 차단 | 자동갱신을 로컬 작업 스케줄러로 이전 |
| 고시 본문 hwp 첨부뿐 | `_chunk_admrul_blob` 안내문 감지 → 스킵(건축구조기준) |
| 조례 조문번호 "000100" 깨짐 | `_ordin_article_no` 6자리(조4+가지2) 정규화 |
| 판례 본문 빈 응답 | 대법원만 본문 XML 제공 → `법원명=="대법원"` 필터 |

---

## 다음 작업 후보

1. **조례 지자체 확장** — `ORDIN_GROUP`에 부산·인천 등 추가
2. **판례·해석례 확대** — PREC_CAP/EXPC_CAP 상향, 키워드 추가
3. **검색 고도화** — 초성 검색, 동의어 (예: "건폐율"↔"건축면적의 비율")
4. **인용 관계 시각화** — 특정 조문 선택 시 인용/피인용 미니 그래프 패널
