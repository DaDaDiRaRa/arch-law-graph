# arch-law-graph

건축 법령 관계 그래프 탐색기 + AI 자연어 질의 웹앱.
법제처 DRF API → graph.json(42,000+ 노드) → React/Vite SPA + FastAPI 백엔드.

실무자(건축설계 소장·중간관리자)가 건축 법령군을 빠르게 탐색하고, 용도지역별 건폐율·용적률·주차·이격·조경 기준을 전국 84개 시 기준으로 국가 vs 도시 즉답하며, AI 자연어 질의로 복합 법령 해석을 얻는 앱.

## 주요 기능

| 모드 | 설명 |
| ---- | ---- |
| 🔍 검색 | 42,000+ 조문 풀텍스트 (동의어·초성 지원, 피인용 순 정렬, 별표 인라인 렌더링, 인용 관계 그래프·영향 트리) |
| 📐 기준 조회 | 용도지역·건물용도·연면적 선택 → 국가 vs 도시 기준 카드, 근거 조문 칩 클릭 → 원문. 주소 입력 시 VWorld로 용도지역 자동 조회 |
| 💬 AI 질의 | Voyage 벡터 RAG(RRF 하이브리드 + 도메인 핀) + Claude SSE 스트리밍, 답변 내 조문 인라인 링크 + 인용 검증 |

### 기준 조회 카드 커버리지 (전국 84개 시)

| 카드 | 도시 수 | 추출 방식 |
| ---- | ------- | --------- |
| 용도지역(건폐율·용적률·일조) | 84 | 정규식 자동 추출 |
| 조경 | 80 | 정규식 자동 추출 |
| 주차(부설주차장) | 66 | LLM 보조 추출 |
| 이격(대지 안의 공지) | 77 | LLM 보조 추출 |
| 완화·혜택 | 82 | LLM 보조 추출 |
| 건축위원회 심의 대상 | 77 | LLM 보조 추출 |

각 카드 값에는 출처 배지(손큐레이션·기계추출·LLM보조)와 시행일이 표기됩니다.
군(郡) 지역은 검색·RAG·원문 corpus만 지원하며 카드는 생성하지 않습니다.

## 구조

```text
builder/             # Python — 법제처 fetch → graph.json 빌드
  build_graph.py     # 법령·고시·조례·판례·해석례 전체 빌드
  inventory_ordin.py # 전국 시·군 × 4조례 자동 검색·매칭 → ordin_group.py 생성
  ordin_group.py     # 조례 목록(자동생성). build_graph.py가 import
  gen_*_llm.py       # Claude(temp0)로 별표 → 카드 데이터 추출 (주차·이격·심의·완화)
  gen_card_data.py   # 정규식 추출 → zoning_auto.js·landscape_auto.js
  build_embeddings.py  # 조문 → Voyage 임베딩 → data/embeddings.npy
  law_go_kr_client.py  # 법제처 DRF 클라이언트 (HWP/HWPX 별표 폴백 포함)
  tests/             # 카드 회귀 스냅샷 테스트(pytest, 골든 대조)

backend/             # FastAPI — AI 자연어 질의 API (SSE 스트리밍)
  main.py            # /api/ping, /api/zoning, /api/lookup, /api/chat
  rag_engine.py      # RRF 하이브리드(벡터+키워드 top-30 융합) + 도메인 핀 + 인용 검증 → Claude API (키워드 FTS 폴백)

web/src/             # React/Vite SPA
  views/             # SearchView, ChatPanel, ComplianceCard, ParkingCard, RefChip, SourceBadge, ...
  *.js               # 손큐레이션 기준 데이터 (17개 시)
  *_auto.js          # 자동생성 기준 데이터 (builder 산출)

data/
  graph.json         # 노드 42,703 / 엣지 119,911 (빌드 산출, git 추적, ~93MB)
  embeddings.npy     # Voyage 벡터 임베딩 30,784개 (git 추적, ~63MB)

Dockerfile           # multistage: node:20-alpine 빌드 → python:3.12-slim + nginx
nginx.conf           # :8080, gzip, /api/ → uvicorn, SPA fallback
```

## 데이터 규모

- 법령 29 + 고시 17 + 조례 554(전국 84개 시 + 82개 군 × 4종) + 판례 100 + 해석례 150
- 노드 42,703 / 엣지 119,911
- 벡터 임베딩 30,784 (Voyage voyage-3-large, 1024차원)

## 빠른 시작 (로컬 개발)

```powershell
# 터미널 1 — 백엔드 (프로젝트 루트에서)
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\uvicorn.exe backend.main:app --port 8001 --reload

# 터미널 2 — 프론트엔드
cd web && npm run dev    # → http://localhost:5173
```

`.env` 파일 (프로젝트 루트):

```shell
LAW_API_KEY=...        # 법제처 DRF API 키 (빌드 시 필수)
ANTHROPIC_API_KEY=...  # Claude API 키 (런타임 필수)
VOYAGE_API_KEY=...     # 벡터 RAG 임베딩 (없으면 키워드 FTS 폴백)
VWORLD_API_KEY=...     # 주소→용도지역 자동조회 (/api/zoning)
```

## graph.json 재빌드

```powershell
# 전체 재빌드
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/build_graph.py

# 단일 법령 테스트
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/build_graph.py --only 건축법

# 벡터 임베딩 재생성 (graph 갱신 후)
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/build_embeddings.py

# 기준 카드 재생성 (graph 갱신 후)
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/gen_card_data.py   # 용도지역·조경
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/gen_parking_llm.py
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/gen_setback_llm.py
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/gen_review_llm.py
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/gen_incentive_llm.py

# 새 지자체 조례 발견 (전국 자동 매칭 → ordin_group.py 갱신)
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/inventory_ordin.py
```

## 테스트

```powershell
# 카드 회귀 스냅샷 (루트에서). 9검사: zoning/landscape × (frozen·extractor_sync·plausible)
#                              + LLM카드(주차·이격·심의·완화) × (frozen·structural·plausible)
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe -m pytest
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe -m pytest --update-golden  # 카드 값 변경 승인
```

GitHub Actions(`.github/workflows/test.yml`)가 push·PR마다 pytest를 실행합니다(커밋된 graph.json+JS만 읽어 법제처 API 불필요).

## Docker (프로덕션 검증)

```powershell
docker build -t arch-law-graph .
docker run -p 8080:8080 -e ANTHROPIC_API_KEY=sk-ant-... arch-law-graph
# → http://localhost:8080
```

## 배포

Cloud Run (GitHub push → 자동 재배포).
`ANTHROPIC_API_KEY`·`VOYAGE_API_KEY`·`VWORLD_API_KEY`를 Cloud Run 환경변수에 별도 설정 필요 (`.env`는 컨테이너 미포함). VOYAGE 미설정 시 키워드 FTS로 자동 폴백.

## 자동갱신

로컬 Windows 작업 스케줄러 (매일 09:00, `scripts/refresh_local.ps1`).
빌드 → 카드 회귀 테스트 게이트 → 변경 시만 commit·push.
GitHub Actions 크론은 비활성화 — 법제처 API가 GH 러너(해외 IP)를 차단함.

---

> ⚠️ 참고용 정보. 정확도·법적 효력을 주장하지 않습니다. 실무 진단은 별도 확인 필요.
