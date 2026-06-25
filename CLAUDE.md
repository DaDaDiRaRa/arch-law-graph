# arch-law-graph — Claude 컨텍스트

건축 법령 관계 그래프 탐색기 + AI 자연어 질의.
법제처 DRF API → `data/graph.json` → React/Vite SPA + FastAPI 백엔드.
실무자(건축설계 소장·중간관리자)가 **건축 법령군(19개)을 주제별·피인용 순으로 빠르게 탐색**하고, **기준 조회**(용도지역·용도·규모별 건폐율·용적률·일조·주차·이격·조경을 국가 vs 도시로 즉답, 모두 근거 조문에 추적 가능)하며, **자연어 질의**(Claude RAG)로 복합 법령 해석을 얻는 게 핵심 목적.

---

## 프로젝트 구조

```text
builder/          # Python — 법제처 fetch → graph.json 빌드
  build_graph.py  # 법령 19 + 고시 + 조례 + 판례 + 해석례 전체 빌드. --only 건축법 으로 단일 법령만 가능
  law_go_kr_client.py  # 법제처 DRF 클라이언트 (law/admrul/ordin/prec/expc, 별표 + HWP 폴백)
  fetch_test.py   # 빠른 fetch 검증
  requirements.txt

backend/          # Python — FastAPI 자연어 질의 API (런타임)
  __init__.py
  main.py         # FastAPI app — /api/ping, /api/chat (SSE 스트리밍)
  rag_engine.py   # graph.json 인-메모리 FTS → Claude API (claude-sonnet-4-6, temp=0)
  requirements.txt  # fastapi, uvicorn[standard], anthropic, python-dotenv

web/src/
  App.jsx            # 최상위 shell — SearchView 하나 감싸는 구조
  views/SearchView.jsx  # 메인 뷰 — 검색 모드 + 기준 조회 모드 토글 + 💬 채팅 버튼
  views/ChatPanel.jsx   # AI 자연어 질의 패널 (사이드 드로어, SSE 스트리밍, 인라인 ref 링크)
  views/ComplianceCard.jsx  # 용도지역 카드 (건폐율·용적률·일조)
  views/ParkingCard.jsx     # 주차 카드 (건물 용도별)
  views/SetbackCard.jsx     # 대지 공지(이격) 카드
  views/LandscapeCard.jsx   # 조경 카드 (연면적 규모별)
  zoning.js parking.js setback.js landscape.js  # 도시별(서울·부산·인천) 큐레이션 기준 데이터(국가 vs 도시)
  lib/lawContent.jsx    # 별표 테이블 파서·렌더러, LawBody 컴포넌트
  data.js              # 공유 데이터: internalLaws, articlesByLaw, nodeById,
                       # citeIn, maxCite, outRel, inRel, lawOf(), lawColor(),
                       # familyOf(), tier(), DOMAINS, domainCount, etc.
  App.css              # 노션/토스풍 화이트 테마. --accent: #3182f6
  vite.config.js       # /api → localhost:8001 프록시 (개발용)

scripts/
  refresh_local.ps1   # 로컬 자동갱신 (작업 스케줄러용): 빌드 → 변경 시 commit·push
data/graph.json   # 빌드 산출물. git에 추적됨 (배포 시 번들)
.github/
  workflows/refresh.yml         # GH Actions 크론 — 비활성화됨(법제처 IP 차단). 수동 dispatch만.
  scripts/graph_hash.py         # built_at 제외 MD5 해시 — 변경 감지용
Dockerfile        # multistage: node:20-alpine 빌드 → python:3.12-slim + nginx 런타임
startup.sh        # Docker CMD: uvicorn(8001) + nginx(8080) 동시 실행
nginx.conf        # port 8080, gzip, /api/ → uvicorn 프록시(SSE buffering off), SPA fallback
```

---

## 현재 상태 (2026-06-25 기준)

- **graph.json**: node≈3393, edge≈10405 — 법령 19 + 고시 17 + 조례 10(서울 4·부산 3·인천 3) + 대법원 판례 40 + 법령해석례 60 (Phase 1–4 완료 + Stage 1–2b + HWP 폴백)
- **기준 조회(결정-등급 카드)**: 검색-퍼스트 외 `📐 기준 조회` 모드. 용도지역→건폐율·용적률·일조 / 건물용도→주차·이격 / 연면적→조경을 **국가 vs 도시 적용**으로 나란히 + 근거 조문 칩(클릭→원문 Reader) + 연결 판례·해석례 자동 수집. **멀티리전(서울·부산·인천) 전 도시 4탭 모두 지원**(인천 주차는 도시지역/관리지역 2단).
- **AI 자연어 질의(Stage 3)**: 오른쪽 하단 `💬` 버튼 → 사이드 드로어. graph.json 인-메모리 FTS(top_k=12) → Claude API SSE 스트리밍. 답변 내 `법령명 제N조` 패턴 자동 파싱 → 클릭 시 Reader에서 원문 열람. Reader에서 열린 조문은 selected_id로 자동 컨텍스트 주입. 하단 근거 조문 칩 병행.
- **HWP 별표 폴백**: 부산·인천 조례 별표는 본문이 HWP 첨부뿐(별표구분='서식'으로 표기). 빌더가 `별표첨부파일명` URL → 다운로드 → `pyhwp(hwp5html)` 변환 → HTML 표를 **선문자(박스드로잉) 텍스트**로 렌더해 graph.json 별표 content 채움. ⚠ `-m hwp5.hwp5html`는 Windows에서 빈 출력 → 콘솔 `.exe` 직접 호출.
- **법제처 API 접근**: 이 로컬 머신(국내 IP)에서 직접 작동 → 재빌드·조례 fetch 가능. GH Actions만 차단됨.
- **배포**: Cloud Run (GitHub push → 자동 재배포). Cloud Run 환경변수에 `ANTHROPIC_API_KEY` 설정 필요.
- **자동갱신**: 로컬 Windows 작업 스케줄러 "arch-law-graph 자동갱신" (매일 09:00, `scripts/refresh_local.ps1`). GitHub Actions 크론은 비활성화 — 법제처 API가 GH 러너(해외 IP)를 차단해 빈 결과 반환하기 때문.
- **빌드 venv**: `D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe` (networkx·httpx·dotenv·fastapi·anthropic 설치)
- **GitHub**: `https://github.com/DaDaDiRaRa/arch-law-graph`

### 법령군 (19개) — `builder/build_graph.py` LAW_GROUP

- 건축법 패밀리: 건축법/시행령/시행규칙 + 피난ㆍ방화구조 규칙·설비기준 규칙·구조기준 규칙·건축물대장 규칙
- 국토계획: 국토계획법/시행령/시행규칙
- 주차장법/시행령/시행규칙
- 건축물의 분양법/시행령/시행규칙
- 녹색건축물 조성 지원법/시행령/시행규칙

### 확장 로드맵 (실무 가치 순)

1. ✅ Phase 1 — 누락 위임 부령·하위법령 보강 (target=law, 완료 2026-06-25)
2. ✅ Phase 2 — 국토부 핵심 건축 고시 17개 (admrul, 완료 2026-06-25). 조문형식 아닌 고시는 장(章) blob, hwp 첨부뿐인 고시는 자동 스킵.
3. ✅ Phase 3 — 서울특별시 건축 조례 4종 (ordin, 완료 2026-06-25). 조문번호 6자리(조4+가지2)는 `_ordin_article_no`로 정규화.
4. ✅ Phase 4 — 대법원 판례 40 + 법령해석례 60 (prec/expc, 완료 2026-06-25). 참조조문에서 (법령명, 제N조) 추출 → `applied`/`interpreted` 엣지.
5. ✅ Stage 1 — 기준 조회(결정-등급 카드) 도입 (완료 2026-06-25).
6. ✅ Stage 2a — 서울 주차·이격·조경 카드 추가 (완료 2026-06-25).
7. ✅ Stage 2b — 멀티리전(부산·인천) 확장 (완료 2026-06-25). 조례 6종 + HWP 폴백.
8. ✅ Stage 3 — AI 자연어 질의 채팅 패널 (완료 2026-06-25). FastAPI RAG + Claude SSE + 인라인 ref 링크.

### 노드 category 체계

법령(없음)·고시(`고시`)·조례(`조례`)·판례(`판례`)·해석례(`해석례`). data.js 의 lawColor/familyOf 가 색상·라벨 분기. 판례/해석례→조문 엣지(applied/interpreted)는 조문의 '피인용'(citeIn/inRel)에 집계됨.

---

## 핵심 아키텍처 결정

### 데이터 흐름

```text
법제처 DRF API → build_graph.py → data/graph.json
                                        ↓ (vite build 시 번들)
                              nginx 정적 서빙 (Cloud Run :8080)

사용자 자연어 질문
  → /api/chat (nginx → uvicorn :8001)
  → rag_engine: graph.json 인-메모리 FTS (top_k=12)
  → Claude API (claude-sonnet-4-6, streaming)
  → SSE 스트리밍 응답 → ChatPanel 인라인 ref 렌더링
```

**런타임 호출**: Anthropic Claude API만 (`ANTHROPIC_API_KEY`). 법제처 API는 빌드 시에만.

### UI — 3가지 모드

1. **🔍 검색**: 조문 번호/제목/본문 풀텍스트. 검색 문법: `"정확한 구절"`, `-제외어`, AND(스페이스). 결과 정렬: 피인용 수 내림차순. 별표 인라인 렌더링, ★ 북마크, 도메인 칩 필터.
2. **📐 기준 조회**: 용도지역/건물용도/연면적 선택 → 국가 vs 도시 기준 카드. 근거 조문 칩 클릭 → Reader.
3. **💬 AI 질의**: 사이드 드로어(backdrop 없음 → Reader 스크롤·클릭 가능). 현재 열린 조문 자동 컨텍스트 주입. 답변 내 법령 참조 자동 링크.

### ChatPanel 동작 원리

- `buildRefMap(source_ids)`: 조문 노드에서 `"법령명 제N조"` 패턴 맵 생성 (전체명 + 단축명)
- `renderAnswerText(text, sourceIds, onOpenRef)`: regex split → 매칭 패턴을 `.answer-ref` 버튼으로 렌더
- 스트리밍 중: plain text + `▋` 커서. 완료 후: 인라인 ref 링크 활성화.
- `onOpenRef(id)`: `setSelected(nodeById.get(id))` + 검색 모드로 전환 → Reader에서 원문 열람

### 별표 파싱

법령·서울 조례·고시: 법제처 `<별표내용>` XML 태그 인라인. 부산·인천 조례: HWP 폴백(`pyhwp hwp5html` → 박스드로잉 텍스트). East Asian Width-aware 테이블 파서(`charW`, `colBoundaries`, `parseTable`), 커버리지 95%.

---

## 현재 사용 중인 API

### 법제처 DRF Open API — 빌드 시에만 (`LAW_API_KEY`)

- `target=law` — 법령 (`MST=` 파라미터)
- `target=admrul` — 행정규칙/고시 (`ID=` 파라미터, MST 아님)
- `target=ordin` — 자치법규/조례 (조문번호 6자리 정규화 필요)
- `target=prec` — 판례 (대법원만 본문 XML 제공)
- `target=expc` — 법령해석례
- ⚠ GH Actions 등 해외 IP 차단 → 로컬에서만 빌드

### Anthropic Claude API — 런타임 (`ANTHROPIC_API_KEY`)

- `backend/rag_engine.py`에서 `AsyncAnthropic` 스트리밍
- 모델: `claude-sonnet-4-6` (env `ANTHROPIC_MODEL`로 override 가능)
- Cloud Run 환경변수에 설정 필요 (.env는 .dockerignore에 의해 컨테이너 미포함)

---

## 빌드 / 실행

```powershell
# ── graph.json 빌드 (자매앱 venv 사용) ─────────────────────────────────
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/build_graph.py
# 단일 법령 테스트
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/build_graph.py --only 건축법

# ── 로컬 개발 (두 터미널 필요) ────────────────────────────────────────
# 터미널 1 — 백엔드 (프로젝트 루트에서)
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\uvicorn.exe backend.main:app --port 8001 --reload

# 터미널 2 — 프론트엔드
cd web && npm run dev    # http://localhost:5173

# ── Docker (프로덕션 검증용) ──────────────────────────────────────────
docker build -t arch-law-graph .
docker run -p 8080:8080 -e ANTHROPIC_API_KEY=sk-ant-... arch-law-graph
# → http://localhost:8080
```

**중요**: 항상 프로젝트 루트 `d:\APPS\arch-law-graph`에서 실행. `.env` 위치가 루트.

---

## 환경 변수

```text
LAW_API_KEY=...          # 법제처 DRF API 키 (필수, 빌드 시에만 사용)
ANTHROPIC_API_KEY=...    # Claude API 키 (런타임 필수 — Cloud Run 환경변수로 설정)
ANTHROPIC_MODEL=...      # 선택, 기본값 claude-sonnet-4-6
```

**Docker/Cloud Run**: `.env`는 `.dockerignore`에 의해 컨테이너 미포함.
`ANTHROPIC_API_KEY`는 반드시 Cloud Run 환경변수(GCP Console → 새 버전 수정 및 배포 → 변수 및 보안 비밀)에 별도 설정.

---

## 자동 갱신 (로컬 작업 스케줄러)

GitHub Actions 크론은 **비활성화** — 법제처 API가 GH 러너(해외 IP)를 차단해 빈 결과를 반환하기 때문.

- **작업**: Windows 작업 스케줄러 "arch-law-graph 자동갱신", 매일 09:00 (`StartWhenAvailable`)
- **스크립트**: `scripts/refresh_local.ps1` — 해시 전 → `build_graph.py` → 해시 후 → 변경 시만 commit·push(→ Cloud Run 재배포). 변경 없으면 graph.json 원복(트리 청결).
- **안전장치**: 빌드가 빈 결과면 `build_graph.py` exit 1 → 파일 미작성·커밋 안 함.
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
| 자동갱신이 빈 graph.json 커밋 → 배포 0건 | 정상본 복구 + `build_graph.py` exit 1 + workflow node_count 가드 |
| 법제처 API가 GH Actions IP 차단 | 자동갱신을 로컬 작업 스케줄러로 이전 |
| 고시 본문 hwp 첨부뿐 | `_chunk_admrul_blob` 안내문 감지 → 스킵(건축구조기준) |
| 조례 조문번호 "000100" 깨짐 | `_ordin_article_no` 6자리(조4+가지2) 정규화 |
| 판례 본문 빈 응답 | 대법원만 본문 XML 제공 → `법원명=="대법원"` 필터 |
| 부산·인천 조례 별표 빈 값(HWP 첨부뿐) | 빌더 HWP 폴백 — pyhwp hwp5html → 박스드로잉 텍스트 |
| `python -m hwp5.hwp5html` Windows 빈 출력 | 콘솔 `hwp5html.exe`(venv Scripts) subprocess 직접 호출 |
| ChatPanel 오버레이가 Reader 스크롤 차단 | 사이드 드로어 방식으로 변경 (backdrop 제거) |
| Docker `.env` COPY 실패 (.dockerignore) | `.env` 제거, Cloud Run 환경변수로 분리 |

---

## 다음 작업 후보

1. **조례 지자체 확장** — `ORDIN_GROUP`에 경기·대구 등 추가. `*_REGIONS`에 적용값 등재.
2. **판례·해석례 확대** — PREC_CAP/EXPC_CAP 상향, 키워드 추가
3. **검색 고도화** — 초성 검색, 동의어 (예: "건폐율"↔"건축면적의 비율")
4. **인용 관계 시각화** — 특정 조문 선택 시 인용/피인용 미니 그래프 패널
5. **채팅 품질 개선** — 벡터 임베딩 기반 RAG, 주소→용도지역 자동 조회 연동(VWorld 이슈 해결 후)
