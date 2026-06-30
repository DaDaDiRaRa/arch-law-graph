# arch-law-graph — 시스템 명세서 (SPEC)

> 코드 역추론 기반 작성. 불확실한 부분은 **(추정)** 표기.
> 작성일: 2026-06-30 / 갱신: 2026-06-30 (B그룹 API화 반영)

---

## 1. 목적

건축설계 실무자(소장·중간관리자)가 **건축 법령을 빠르게 탐색하고, 기준 수치를 즉답 받으며, 복합 법령을 AI로 해석**하도록 돕는 도구.

세 가지 핵심 가치:
1. **탐색 속도** — 42,000+ 조문을 동의어·초성·피인용 순으로 즉시 검색
2. **기준 즉답** — 용도지역·건물용도·연면적 입력 → 국가 상한 vs 도시 조례 비교, 근거 조문 직접 링크
3. **복합 해석** — "실제 적용 가능한지", "단서 조항이 있는지"를 자연어 질의로 확인

**대상 도메인**: 건축법·국토계획법·주차장법·녹색건축물법 등 법령군 29개 + 국토부 고시 17개 + 전국 84개 시 + 82개 군 조례 554개.

> **정체성(자매앱과의 역할 분담)**: 자매앱 arch-law-diagnose가 "이 대지에 지을 수 있나"(대지 GIS·산정·사업성)를 담당. 본 앱(graph)은 **건축 법령의 단일 권위 지식원** — 권위(전체 법령군)·추적가능(원문 근거)·최신(시행일)·호출가능(법령 API). 산정·대지탐지는 구현하지 않되, 그 계산의 *근거 조문 원문*은 graph가 보유(diagnose가 `/api/lookup`으로 당겨씀).

---

## 2. 전체 데이터 흐름

```
[법제처 DRF API]
      │
      ▼ build_graph.py (빌드 시, 로컬 전용)
[data/graph.json]  ──────────────────────────────────────────┐
  ·노드 42,703                                              │
  ·엣지 119,911                                             │
      │                                                       │
      ├── build_embeddings.py ──► data/embeddings.npy         │
      │     (Voyage voyage-3-large, 30,784벡터, L2정규화)     │
      │                                                       │
      ├── gen_card_data.py ──► web/src/zoning_auto.js        │
      │                              landscape_auto.js        │
      │                                                       │
      └── gen_*_llm.py (Claude temp0) ──► parking_auto.js   │
                                           setback_auto.js   │
                                           review_auto.js    │
                                           incentive_auto.js │
                                                             │
[웹 브라우저]                                                 │
  ├── SPA(React/Vite) ◄── nginx :8080 정적 서빙             │
  │     └── data.js: runtime fetch(graph.json ?url 에셋) ◄──┘
  │           JS 번들 ~110KB gzip / graph.json 별도 캐싱
  │
  ├── /api/zoning  → 주소 → VWorld → 용도지역 자동 조회
  ├── /api/lookup  → 조문 원문 배치 조회 (외부 앱 그라운딩)
  └── /api/chat    → nginx → uvicorn :8001 → rag_engine.py
        RRF 검색 → Claude SSE → 브라우저 스트리밍
```

법제처 API는 **빌드 전용** — 런타임에는 graph.json 정적 스냅샷만 사용.
Cloud Run 배포 후 **법령 실시간 반영은 안 됨** (일 1회 로컬 갱신 후 push → 자동 재배포).

---

## 3. 그래프 데이터 모델 (graph.json)

> 직렬화 형식: networkx node-link JSON (`nodes` / `links` 키, `directed: true`).

### 3.1 노드 스키마

```
{
  "id":          "<법령명>/<조문번호>",      // 예: "건축법 시행령/제119조"
  "type":        "article" | "law",
  "law_nm":      "건축법 시행령",
  "article_no":  "119",
  "title":       "면적 등의 산정방법",
  "content":     "<조문 본문>",
  "category":    null | "고시" | "조례" | "판례" | "해석례",
  "domain_tags": ["면적", "높이"],           // 검색·도메인 필터용
  "ef_yd":       "20260324",                 // 조문 시행일자 (중앙법령 조문에만 존재)
  "byeolpyo":    [ { "title", "content" } ] // 별표 첨부 (있으면)
}
```

`category` 없음 = 국가 법령(법·시행령·시행규칙). 색상·family 분기에 사용.
`ef_yd`는 **중앙법령(법령 29종) 조문에만** 저장됨(전체 article의 일부) — 조례·고시·판례·해석례 조문은 미저장(시행일 칩이 라벨만 표시되는 graceful degrade).

### 3.2 엣지 유형

| type | 의미 | 건수 | 예 |
|---|---|---|---|
| `contains` | 법령 → 소속 조문 (구조) | 38,017 | 건축법 → 건축법/제1조 |
| `references` | 같은 법령 내 조문 인용 | 39,166 | 시행령 제119조 → 같은 령 제43조 |
| `cross_law` | 타 법령 인용(「…」) | 28,306 | 건축법 → 국토계획법 |
| `byeolpyo` | 별표 참조 | 11,929 | 시행령 제27조 → 별표1 |
| `delegates` | 위임 | 20 | 건축법 제61조 → 시행령 제86조 |
| `applied` | 판례 적용 조문 | 313 | 대법원 판례 → 건축법 제14조 |
| `interpreted` | 해석례 대상 조문 | 2,160 | 법령해석례 → 건축법 제2조 |

**피인용 수(citeIn)**: `contains`를 제외한 in-degree(나머지 6개 타입 합산)가 조문 랭킹(검색 정렬)에 활용됨. 프론트 `data.js`의 `citeIn`·`inRel`/`outRel`, 백엔드 `rag_engine`의 `_in_rel`/`_out_rel`(B-5 `/api/citations`)이 동일 의미론.

### 3.3 법령 구성 (29개)

| 패밀리 | 포함 법령 |
|---|---|
| 건축법 | 건축법·시행령·시행규칙 + 피난방화·설비·구조·대장 규칙 |
| 국토계획 | 국토계획법·시행령·시행규칙 |
| 주차장 | 주차장법·시행령·시행규칙 |
| 분양·녹색 | 건축물분양법·녹색건축물조성지원법 (각 시행령 포함) |
| 심의 별도 | 도시교통정비법·환경영향평가법·경관법·지하안전법·자연재해법 + 시행령 |

### 3.4 조례 구성 (554개)

전국 **84개 시 + 82개 군** × 도시계획(군=군계획)·건축·주차·녹색건축 4종 + 경기도 도단위 2.
- **시(309조례)**: 검색·RAG + 기준 조회 카드 생성.
- **군(246조례, Stage 13)**: 검색·RAG·원문 corpus 전용 — 카드 미생성(`gen_card_data.py`가 시만 처리). 광역시 산하 군(달성·군위·강화·옹진)은 자체 군계획 조례 없음(광역시 도시계획조례 적용).

---

## 4. 빌더 파이프라인 (builder/)

### 4.1 graph.json 빌드 (`build_graph.py`)

```
법제처 DRF API (target=law/admrul/ordin/prec/expc)
  │
  ├── law_go_kr_client.py
  │     ─ XML 파싱(조문·별표)
  │     ─ HWP 첨부 폴백: hwp5html.exe → 박스드로잉 텍스트
  │     ─ HWPX(zip/OWPML) 폴백: hp:tbl 파싱
  │     ─ East Asian Width 기반 열 경계 계산
  │
  ├── 조례 목록: ordin_group.py (inventory_ordin.py가 자동생성)
  │     ─ 전국 84개 시 + 82개 군 × 4종
  │     ─ 주차 조례는 표준접미사 화이트리스트로 부속조례 배제
  │     ─ 군 용도지역 조례명 다양 → COUNTY_PLAN_CANON 접미사로 흡수
  │
  ├── 판례/해석례: 키워드 확대(E-10), 판례 cap=160, 해석례 cap=240
  │     ─ 참조조문 파싱 → applied/interpreted 엣지 생성
  │
  └── graph.json 직렬화
        ─ built_at 타임스탬프 포함 (해시 비교 시 제외)
        ─ 빈 결과면 exit 1 (자동갱신 안전장치)
```

### 4.2 기준 카드 데이터 생성

**경로 A — 정규식 추출** (`gen_card_data.py`): 건폐율·용적률·조경
- graph 조문 본문에서 `100분의 N`, `N%`, `N퍼센트` 등 수치 추출
- 표기 정규화: "공백 이름" 매칭, "의" 조사 선택, 공장 줄 제외, `100분의 N`(천단위 쉼표 포함) 인식
- 소스 미발견 시 `null` → 프론트엔드가 "준비 중" guard

**경로 B — LLM 추출** (`gen_*_llm.py`): 주차·이격·심의·완화
- graph 별표 원문 → Claude(claude-sonnet-4-6, temperature=0) → 표준 JSON 스키마
- 손큐레이션 도시와 정확일치 검증으로 환각 없음 확인 (추정: 수동 대조 기반)
- 프롬프트에 표준 타입(9개 주차 용도 등) 사전 주입 → 모델은 수치만 채움

산출 카드 데이터에는 값별 출처 태그(`src`: manual/machine/llm)가 부착되어 프론트엔드 출처 배지로 표시됨.

### 4.3 벡터 임베딩 (`build_embeddings.py`)

- 조문 텍스트: `법령명 + 제N조 제목 + 본문` (최대 1600자 truncate)
- 모델: Voyage voyage-3-large, dim=1024
- 배치 64, 5회 재시도, L2 정규화 후 float16 저장
- 산출: `embeddings.npy` (30,784행 행렬) + `embeddings_meta.json` (id·모델·차원)

### 4.4 자동갱신 (`scripts/refresh_local.ps1`)

```
Windows 작업 스케줄러 매일 09:00
  │
  ├── 해시(built_at 제외) 비교 → 변경 없으면 graph.json 원복 후 종료
  ├── build_graph.py 실행
  │     ─ 실패(exit 1) → 파일 미작성, 커밋 안 함
  │
  ├── 카드 회귀 테스트(pytest) 게이트 — 카드 값 드리프트 시 커밋 차단
  │
  └── 변경 있으면 git commit + push → Cloud Run 자동 재배포
```

GitHub Actions 크론 비활성화 — 법제처 API가 GH 러너(해외 IP) 차단.

### 4.5 카드 회귀 테스트 (`builder/tests/`)

전체 11검사:

- **zoning 84·landscape 80**: 카드당 3검사 — frozen(live==골든, 사람 미승인 변경 차단)·extractor_sync(추출기 재실행==커밋카드)·plausible(건폐율 20~90·용적률 50~1500·조경 3~30 경계).
- **LLM 카드(주차·이격·심의·완화)**: LLM 출력이라 재현 불가 → extractor_sync 대신 frozen+structural+plausible. incentive는 함수 호출이라 `dump_cards.mjs`(node)로 실제 평가 후 골든 대조.
- **standards.json(B-6)**: 2검사 — sync(`gen_standards.mjs --stdout` 재평가 == 커밋된 `data/standards.json`, 카드 JS↔JSON 드리프트 검출)·structural(도메인·region 구조 불변식).
- 골든 승인: `pytest --update-golden`. GitHub Actions(`test.yml`)가 push·PR마다 실행(커밋된 graph.json+JS만 읽어 법제처 불필요).
- **버그 적발 실적**: 군포 중심상업 용적률 1%(천단위 쉼표 오파싱) garbage를 plausible이 검출 → 추출기 수정.

---

## 5. 프론트엔드 아키텍처 (web/src/)

### 5.1 데이터 로딩 (`data.js`)

graph.json(~93MB)을 Vite `?url` 에셋으로 번들 분리 → 브라우저 런타임 fetch(top-level await).
JS 번들 7.3MB gzip → ~110KB gzip (98.5% 감소). graph.json은 브라우저 캐시 개별 관리(12.6MB gzip 첫 로드).

`data.js`가 노출하는 공유 유틸:

| 심볼 | 용도 |
|---|---|
| `nodeById` | id → 노드 O(1) 조회 |
| `articlesByLaw` | 법령명 → 조문 배열 |
| `citeIn` | 노드 id → 피인용 수 |
| `inRel` / `outRel` | 인용/피인용 엣지 목록 |
| `lawColor()` | category → 색상 팔레트 |
| `familyOf()` | 법령명 → 패밀리 레이블 |
| `tier()` | 법령 계층(법/령/칙) |
| `DOMAINS` / `domainCount` | 도메인 태그 필터용 |
| `fmtEf()` / `efDate()` | 조문 시행일자 포맷(`2026-03-24`) |

### 5.2 3가지 UI 모드

#### 모드 1: 🔍 검색 (`SearchView.jsx`)

검색어 파싱 규칙:
- `"정확한 구절"` — 따옴표 내 exact match
- `-제외어` — 해당 단어 포함 결과 제외
- 스페이스 분리 — AND 조건

정렬: 피인용 수(`citeIn`) 내림차순.

부가 기능: 동의어 그룹(20개)·초성 검색, 도메인 칩 필터, ★ 북마크(localStorage), URL 딥링크(`?q=`, `?node=`).

조문 클릭 → Reader 패널:
- 별표 인라인 렌더링, 근거 조문 칩(시행일 표기, `RefChip`)
- `CiteGraph` — 인용 관계 SVG (좌=피인용·우=인용)
- `RelLegend` — 관계 타입 범례(참조·타법령·별표·위임·판례·해석례) + 타입별 카운트 + 클릭 필터
- `ImpactTree` — 개정 영향 트리(`inRel` 역방향 BFS, 깊이3·cap80): "이 조문 개정 시 영향받는 조문"

#### 모드 2: 📐 기준 조회 (`SearchView.jsx` 서브탭)

선택 흐름: 지역 스위처(REGIONS) → 서브탭(용도지역/주차/이격/조경/완화/심의)
**주소 자동조회**: 상단 주소 입력창 → `/api/zoning`(VWorld) → 용도지역 조회 → REGIONS 매칭 + zone 자동 선택 → 카드 즉시 렌더. 카드 미지원 지역(군 등)은 "시 단위 카드 미지원(용도지역만 확인)" 안내 후 카드 변경 안 함.

**지역 코드 체계**:
- 특·광역시·특별자치: 2자리 (`"11"` = 서울)
- 기초시: 5자리 법정동코드 (`"41110"` = 수원)
- 조회 미지원 지역: `"준비 중"` guard 표시

**카드 6종**:

| 카드 | 입력 | 출력 |
|---|---|---|
| ComplianceCard | 용도지역 | 건폐율·용적률·일조 (국가 vs 도시) |
| ParkingCard | 건물 용도 | 부설주차 설치기준 (국가 vs 도시) |
| SetbackCard | 건물 용도 | 대지 안의 공지 이격 (국가 vs 도시) |
| LandscapeCard | 연면적 | 조경 의무면적 비율 (국가 vs 도시) |
| IncentiveCard | 용도지역 | 완화·혜택 (공개공지·녹색·임대 등) |
| ReviewCard | 용도·규모 | 건축위원회 심의 대상 체크리스트 |

각 카드 도시명 옆에 `SourceBadge`(manual/machine/llm 출처 배지 + 툴팁).

**데이터 계층** (두 레이어 merge):
```js
// *.js       — 손큐레이션 (기존 17개 시, 정확도 높음, src="manual")
// *_auto.js  — 자동생성 (신규 시, builder 산출, src=machine/llm)
export const REGIONS = [...REGIONS_BASE, ...REGIONS_AUTO]
```

근거 조문 칩: 클릭 → Reader 열기 + 연결 판례·해석례 자동 수집(inRel).

#### 모드 3: 💬 AI 질의 (`ChatPanel.jsx`)

- 사이드 드로어(backdrop 없음) — Reader 동시 사용 가능
- 현재 열린 조문 id(`selected_id`) 자동 컨텍스트 주입
- 답변 스트리밍 중: plain text + `▋` 커서
- 완료 후: `"법령명 제N조"` 패턴 자동 파싱 → 인라인 참조 버튼 활성화(시행일 툴팁)
- 클릭 → `nodeById.get(id)` → Reader에서 원문 열기
- 답변 하단: 근거 조문 칩(`RefChip`) + **인용 검증 경고**(graph에 실재하지 않는 인용은 호박색 `.chat-unverified` 표시)

### 5.3 별표 파싱 (`lib/lawContent.jsx`)

법제처 XML `<별표내용>` 안의 선문자(박스드로잉) 표를 HTML 테이블로 변환.

```
선문자 표 텍스트
  │
  ├── 세로선(│) 위치 → 열 경계 감지 (East Asian Width: 한글=2칸)
  ├── 가로선(─) 위치 → 행 경계
  └── 셀 내용 추출 → <table><tr><td> 생성
              실패 시 <pre> 폴백
```

---

## 6. 백엔드 / RAG 파이프라인 (`backend/`)

### 6.1 FastAPI 앱 (`main.py`)

```
/api/ping                      — 헬스체크
/api/zoning                    — 주소 → VWorld → 용도지역 자동조회 (Referer=SERVICE_URL, 속성명 uname)
/api/lookup                    — 조문 원문 배치 조회 (외부 앱 그라운딩용, 배치 50)
/api/chat                      — SSE 스트리밍 질의응답 (RAGEngine.answer_stream)
/api/article/{id}              — 노드 단건: 메타 + 본문 + 시행일 ef_yd (B-5)
/api/citations/{id}            — 인용 out / 피인용 in (contains 제외·type별, B-5)
/api/standard/{domain}?code=   — 카드 기준 데이터(국가 vs 도시) API (B-5, data/standards.json)
```

`/api/article`·`/api/citations`는 id에 `/`가 포함돼 `{id:path}` 컨버터 사용. 셋 다 읽기 전용 GET이며 이미 로드된 graph/standards에서 서빙(신규 fetch·재빌드 0). `/api/standard`는 diagnose가 전국 비교를 graph에서 당겨쓰는 진입점.

RAGEngine 싱글톤 — `lifespan` 컨텍스트 핸들러(B-7, `@app.on_event` deprecated에서 이전)에서 graph.json + embeddings.npy 전부 메모리 로드. `_standards`(standards.json)도 같은 시점 로드. CORS 전체 허용 (추정: 개발 편의 + Cloud Run 도메인 미리 모름).

### 6.2 RAG 엔진 (`rag_engine.py`)

#### 검색 (search)

```
query
  │
  ├── _norm_query(): 도메인 약어 정규화 (건폐→건폐율, 이격거리→대지공지 등)
  │
  ├── [벡터 있음] _rrf_search()
  │     ├── _vector_search(POOL=30): Voyage 임베딩 코사인, 런타임 질의 임베딩
  │     ├── _keyword_search(POOL=30): 제목·법령명 3×, 본문 1×, 도메인태그 2× 가중 스코어
  │     └── RRF(k=60): score += 1/(60+rank), 합산 후 top-12
  │
  ├── [벡터 없음] _keyword_search(top_k=12)
  │
  └── _apply_pins(): 도메인 핀
        ─ "건폐율" + ("국가"|"시행령"|"상한"|"법령"|"상위법") → 시행령 제84조 강제 포함
        ─ "용적률" + 동일 트리거 → 시행령 제85조 강제 포함
        ─ 이미 결과에 있으면 중복 추가 안 함
```

#### 생성 (answer_stream)

```
top-12 조문 → _fmt(max_chars=6000) → 컨텍스트 블록
  │
  ├── selected_id 있으면 맨 앞에 추가 (현재 열린 조문 우선)
  │
  ├── Claude API (claude-sonnet-4-6, max_tokens=2500, SSE 스트리밍)
  │     system: 건축사 페르소나 + 조문 근거 원칙 + "확인 불가" 규칙
  │       → 조문 없는 내용은 "현재 DB에서 확인 불가"로 답변
  │
  └── verify_citations(): 답변 본문의 "법령명 제N조" 인용을 사후 파싱
        ─ 실재 법령명(본문 가진 article의 law_nm)이 제N조 앞에 올 때만 검증
        ─ 해당 조문 노드 부재 → unverified[] (done 이벤트에 동봉)
        ─ phantom law(인용추출 산물, 본문無) 배제로 오탐 0
```

#### 성능 벤치마크 (`builder/eval_rag.py`, 34문항)

| 검색 방식 | 결론 일치 | factual | 법령 인용 |
|---|---|---|---|
| 키워드 FTS | 38.2% | 21.1% | 58.8% |
| + RRF | 70.6% | 63.2% | 88.2% |
| + 핀 + max_chars | **88.2%** | **94.7%** | **97.1%** |

judge 모델은 opus-4-8 고정(`tool_choice` 강제로 구조화 JSON 출력 보장).

---

## 7. 배포 구조

### 7.1 Docker (multistage)

```
Stage 1: node:20-alpine
  └── cd web && npm ci && npm run build → /dist

Stage 2: python:3.12-slim
  └── pip install -r backend/requirements.txt

Stage 3 (런타임): python:3.12-slim + nginx
  ├── /dist (Vite 빌드 결과)
  ├── data/graph.json + embeddings.npy (빌드 시 COPY)
  ├── backend/ (FastAPI)
  └── startup.sh: uvicorn :8001 + nginx :8080 동시 실행
```

### 7.2 nginx.conf

- `:8080` 수신
- `/api/` → `127.0.0.1:8001` 프록시 (SSE 버퍼링 OFF, 타임아웃 120s)
- `/assets/` — 1년 캐시 (Vite 해시 파일명)
- SPA fallback → `index.html`
- gzip: text/html, CSS, JS, JSON

### 7.3 Cloud Run

- GitHub push → 자동 재배포
- 환경변수: `ANTHROPIC_API_KEY` (필수), `VOYAGE_API_KEY` (없으면 FTS 폴백), `VWORLD_API_KEY` (주소조회), `SERVICE_URL` (VWorld Referer), `ANTHROPIC_MODEL` (기본 claude-sonnet-4-6)
- `.env`는 `.dockerignore`로 컨테이너 미포함 → GCP Console에서 별도 설정

---

## 8. 알려진 한계

### 8.1 데이터 한계

| 항목 | 내용 |
|---|---|
| 법령 실시간성 | 오프라인 스냅샷. 법제처 개정 후 당일 갱신은 불가 (최대 1일 지연) |
| 현행만 보유 | 빌더가 `현행연혁구분!=현행` 필터 → 연혁 타임라인·입법예고 없음 |
| 수원 주차 | 법제처 DB에 일반 주차장 설치 조례 미등록 → 영구 guard |
| 이격 7개 도시 | 여주·동두천·원주·논산·영천·문경·양산 — 조례 자체에 별표 없음 → 영구 guard |
| 부산 단독주택 주차 | 세부 데이터 미보유 (RAG eval pk_busan_1 실패) |
| 군(郡) 지역 | 카드 미생성, 검색·RAG·corpus만 지원 |
| 조례·고시·판례 시행일 | `ef_yd` 중앙법령 조문에만 저장 → 그 외 칩은 라벨만 표시(graceful degrade) |
| HWP 전용 조례 | pyhwp 변환 한계 — Windows 콘솔 exe 직접 호출 필요, CI 환경 불가 (추정) |

### 8.2 검색·RAG 한계

| 항목 | 내용 |
|---|---|
| "DB 확인 불가" 패턴 | 조문에 없는 수치는 모델이 답변 거부 (시스템 프롬프트 설계 의도) |
| 벡터 임베딩 staleness | graph.json 갱신 후 `build_embeddings.py` 재실행 안 하면 검색 품질 저하 |
| 키워드 FTS noise | "국가", "상한" 같은 범용 토큰이 무관한 장문 조문(별표) 상위 랭킹 유발 |
| 복합 쿼리 | 건폐율+일조 동시 질문 시 한쪽 누락 가능 (complex_1 실패 사례) |
| 완화 복합 reasoning | 녹색건축 완화율(6%/3%)처럼 조건부 수치는 오해 가능 (incentive_1) |
| 인용 검증 범위 | verify_citations는 보수적 — 대명사("동법")·접두어 없는 조례명은 anchor 안 됨(미검증) |

### 8.3 빌드 한계

| 항목 | 내용 |
|---|---|
| 법제처 IP 차단 | 해외 IP(GitHub Actions) 차단 → 로컬에서만 빌드 가능 |
| 빌드 시간 | 전체 재빌드 수십 분 소요 (추정: API 호출 수 + HWP 변환) |
| 특정 조례만 업데이트 불가 | `--only` 옵션이 법령 단위만 지원 (추정: 조례 단위 선택 불가) |
| LLM 추출 비용 | gen_*_llm.py 전체 재실행 시 Claude API 비용 발생 (추정: 수백 건 × API 호출) |

### 8.4 운영 한계

| 항목 | 내용 |
|---|---|
| 단일 컨테이너 | uvicorn + nginx 같은 프로세스 공간 → 백엔드 재시작 시 정적 서빙도 중단 |
| 메모리 | graph.json(~93MB) + embeddings.npy(~63MB) 상시 메모리 점유 |
| 검색 병렬성 | uvicorn 단일 워커 기준, 동시 SSE 세션 수 무한 확장 불가 (추정) |
| 클라이언트 로드 | graph.json 12.6MB gzip 첫 로드 — 모바일 체감 저하 시 서버사이드 검색 필요 |
| 법적 책임 | 시스템 프롬프트에 "참고용" 고지 포함, 실무 인허가 적용 책임 없음 |

---

## 9. 설계 결정 근거 (역추론)

### 9.1 graph.json을 ?url 정적 에셋으로 분리한 이유
JS 번들에 대용량 JSON을 인라인하면 Vite 빌드 시 7.3MB gzip → 다운로드 불가. `?url` 분리로 그래프 캐싱·JS 캐싱 독립 관리 가능 (JS 변경 시 그래프 재다운로드 불필요).

### 9.2 손큐레이션 + 자동생성 이중 계층
초기 17개 도시는 직접 큐레이션(정확도 높음). 전국 확장 시 84개를 모두 손큐레이션하면 비용이 과함 → 정규식/LLM 자동 추출 후 손큐레이션을 기준(ground_truth)으로 검증. 값별 출처 배지로 신뢰도 구분.

### 9.3 RRF + 도메인 핀 조합
벡터 검색만 사용하면 "제2종전용주거지역"처럼 조례에 많이 등장하는 용어로 국가법(시행령 제84조)이 밀림. 키워드 FTS만 사용하면 "국가", "상한" 같은 범용 토큰으로 무관 문서가 상위에 올라옴. RRF로 두 방식을 융합하고, 핀으로 BCR/FAR 국가 기준 조문을 보장.

### 9.4 ChatPanel backdrop 제거
사이드 드로어 방식으로 Reader를 가리지 않으면 "AI 답변 보면서 원문 확인" 워크플로가 가능. backdrop이 있으면 Reader 스크롤·클릭이 막혀 사용성 저하.

### 9.5 인용 검증을 사후처리로
RAG 답변 정확도(88%) 추격보다 *틀린 인용 차단*이 신뢰에 직접적. 임베딩·재빌드 없이 순수 사후처리로 phantom 인용을 호박색 경고 표시 → 환각 가시화.

### 9.6 조례 자동 발견(inventory_ordin.py)
도시당 조례명·기관명을 수동 추측하면 시행착오가 큼(특례시는 "경기도 수원시" 형식 등). 전국 시·군 × 4조례를 법제처 API로 자동 검색·매칭 → ordin_group.py 생성으로 병목 해소.

### 9.7 빌드 venv를 자매 앱(arch-law-diagnose)에서 공유
빌더 의존성(networkx·httpx·fastapi·anthropic 등)이 arch-law-diagnose 백엔드와 겹침. 별도 venv 관리 비용 절약 (추정: 의도적 설계).

---

## 10. 완료 / 미구현 / 향후 후보

### 10.1 최근 완료 (2026-06-29 ~ 06-30)

| 항목 | 내용 |
|---|---|
| Stage 12·13 — 전국 확장 | 84개 시 + 82개 군 조례(554), node 42,703. inventory_ordin.py 자동 발견 |
| C-1 — 카드 회귀 테스트 | pytest 11검사(+ standards sync, B-6) + 골든 + refresh 게이트 + GitHub Actions CI |
| C-2 — 출처 배지 | 카드 값별 src(manual/machine/llm) 태깅 + SourceBadge |
| C-3 — 시행일 전파 | ef_yd를 Reader·카드칩·RAG칩에 전파(fmtEf/efDate/RefChip) |
| C-4 — RAG 인용 검증 | verify_citations로 phantom 인용 사후 차단 |
| D-8 — 엣지 타입 범례 | RelLegend(관계 타입 범례 + 필터) |
| D-9 — 개정 영향 트리 | ImpactTree(inRel 역방향 BFS) |
| 주소→용도지역 자동조회 | VWorld 연동(`/api/zoning`), REGIONS 매칭 + zone 자동선택 |
| E-12 — diagnose 인용 점검 | 참조 127조문 graph 실재성 감사, corpus 빈틈 0 확인 |
| B-7 — 응답 안정성 | `@app.on_event` deprecated → `lifespan` 핸들러 이전 |
| B-6 — 카드 단일소스화 | `gen_standards.mjs` → `data/standards.json` 생성물 + sync 회귀 테스트 |
| B-5 — 구조화 조회 엔드포인트 | `/api/article/{id}`·`/api/citations/{id}`·`/api/standard/{domain}?code=` |
| E-10 — 판례·해석례 키워드 확대 | cap 100/150 → 160/240, 키워드 보강 (build_graph.py) |

### 10.2 미구현 / 향후 후보

| 항목 | 상태 |
|---|---|
| 카드 1차소스 역전(B안)·실제 MCP 서버 구현 | 미구현 (B-6이 전조, `doc/B-law-api-plan.md`) |
| diagnose가 신규 엔드포인트 실호출(앱 통합) | 미구현 (B-5 토대 마련됨) |
| 멀티턴 컨텍스트 (이전 대화 주입) | 미구현 |
| 군(郡) 지역 카드 | 미구현 (검색·RAG·corpus만) |
| 입법예고/개정 진행중 추적 | 미구현 (advanced, 현행만 보유) |

---

*이 문서는 코드 역추론 기반으로 작성되었습니다. 공식 설계 문서가 아니며, 실제 동작과 일부 차이가 있을 수 있습니다.*
