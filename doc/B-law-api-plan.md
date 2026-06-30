# B그룹 작업 계획 — 법령 API / 호출가능성

> 작성 2026-06-30. 대상: `arch-law-graph`. 다음 작업 세션에서 이 문서를 참조해 착수.
> 관련 메모리: `mcp_serverization_goal`, `two_app_division`, `e12_diagnose_citation_audit`.

---

## 0. 목적 — 무엇을 위해 하는가 (정체성 교정 포함)

질문: *"B그룹은 이 앱을 더 정교하고 배포 가능하고, 나중에 다른 앱과 합칠 때를 위해 만드는 것 맞나?"*

**대체로 맞다. 단 한 곳 교정한다.**

| 사용자 표현 | 판정 | 설명 |
|---|---|---|
| 나중에 다른 앱과 합칠 때를 위해 | ✅ **핵심** | B-6 단일소스화가 API·MCP·앱통합 **세 목표로 수렴**. diagnose가 `/api/standard`로 전국 비교를 graph에서 당겨씀. |
| 호출가능성 | ✅ **핵심** | graph를 **데이터 제공 서버(provider)** 로. 카드·조문·인용을 사람 UI 밖(diagnose·MCP·통합사이트)에서도 꺼내 씀. |
| 더 정교하게(정확도) | ❌ **교정** | 정확도는 **C그룹** 영역이며 **이미 완료**(C-1 회귀테스트·C-2 출처배지·C-3 시행일·C-4 인용검증). B는 정확도를 올리지 않는다. |
| 배포 가능하게 | △ **부분** | 배포 자체는 이미 Cloud Run으로 됨. B-7(lifespan)이 **배포 안정성**에 해당하나 B의 주목적은 배포가 아니라 데이터 단일소스화 + API 표면 확장. |

### 정체성 경계 (반드시 지킬 것)

- **"법령 API" = 외부 법 API를 새로 붙이는 게 아니다.** 이미 가진 `graph.json`·카드 데이터를 **엔드포인트로 노출**하는 것. 소스는 법제처 하나로 충분(권위는 소스 수가 아니라 *건축 법령 내 깊이*).
- **graph는 산정·대지GIS를 구현하지 않는다**(diagnose 담당). graph는 ① 근거 조문 원문, ② 기준 데이터(카드), ③ 관계(인용)만 제공. diagnose의 VWorld/EUM/LURIS(대지 데이터)는 graph가 끌어오지 않는다.
- graph의 세 소비자: ① 사람(웹 검색·Reader), ② RAG 채팅(법령 해석 Q&A), ③ **기계/타앱(diagnose·미래 MCP)** ← B그룹은 이 ③을 강화한다.
- 표어: **"이 법이 뭐라고 하는가, 어디 근거하며, 무엇과 연결되는가."**

---

## 1. 현재 상태 실사 (2026-06-30 코드 확인)

### 백엔드 엔드포인트 (`backend/main.py`) — 표면이 얇다

| 엔드포인트 | 용도 | 비고 |
|---|---|---|
| `GET /api/ping` | 헬스체크 | |
| `GET /api/zoning?address=` | 주소→VWorld→용도지역 | 대지 데이터(경계 사례) |
| `POST /api/lookup` | 조문명/노드id 목록(최대 50) → 원문 본문 배치 | **이미 diagnose가 사용**(그라운딩). 배치 조회의 선례. |
| `POST /api/chat` | RAG SSE 스트리밍 | |
| `@app.on_event("startup")` | 엔진 로드 | **deprecated** (B-7 대상) |

서버는 `backend/rag_engine.py`에서 `graph.json`을 메모리로 로드:
- `self._by_id = {n["id"]: n for n in nodes}` — **노드 id 단건 조회 즉시 가능**.
- `self.lookup(queries)` — 조문명 정규화(`제N조의M → 제N의M조`) 후 본문 반환.
- → `/api/article`·`/api/citations`는 **이미 로드된 graph에서 바로 서빙 가능**(신규 fetch·재빌드 불필요).

### 카드 데이터 — 사람 UI에만 묶여 있다 (B-6이 푸는 문제)

- 6개 도메인: `web/src/{zoning,parking,setback,landscape,incentive,review}.js` (+ 각 `*_auto.js`).
- 구조: 도메인별 `REGIONS`(또는 `*_REGIONS`) 배열. 각 원소 = `{ code, name, refs, ...행데이터 }`.
  - `code`: 특·광역시 2자리("11"서울), 기초시 5자리 법정동코드("41110"수원).
  - `refs`: 근거 조문 id 배열(예 `"서울특별시 도시계획 조례/제44조"`) — graph 노드 id와 동일 형식.
  - 국가 상한은 `zoning.js`의 `ZONE_DEFS`(`bcrNat`=시행령 제84조, `farNat`=제85조).
- **소비자는 `web/src/views/SearchView.jsx` 단 하나**(`import { REGIONS } from "../zoning.js"` …).
- ⚠ **incentive는 행이 함수 호출**(`relax()`·`gg()`·`green()`)로 동적 생성 → 정적 JSON이 아님.
- → 백엔드·diagnose·MCP가 **카드 값에 접근할 방법이 없다.** 이게 B그룹의 병목.

### 이미 있는 결정적 자산 — `builder/tests/dump_cards.mjs`

- C-1/Opt3 회귀 테스트용으로 **카드 JS 모듈(incentive의 함수 호출 포함)을 node로 평가해 JSON으로 덤프**하는 스크립트가 이미 존재.
- 골든: `builder/tests/golden/{zoning,landscape,cards_llm}.json`.
- **B-6의 materialization 메커니즘을 새로 만들 필요 없음** — 이 스크립트를 확장/재사용하면 `data/standards.json` 생성이 저위험.

---

## 2. 작업 항목

세 항목. 의존: **B-7(독립·가벼움) → B-6(단일소스화) → B-5(엔드포인트)**. B-5는 B-6 산출물(`standards.json`)에 의존.

### B-7. 응답 안정성 — lifespan 이전 (가벼움·선행)

- **무엇**: `@app.on_event("startup")` (deprecated) → `lifespan` 컨텍스트 핸들러로 이전.
- **왜**: starlette deprecation. 과거 502 이력 때문에 starlette 버전을 핀으로 막아둔 상태 → lifespan 이전 후 **핀 해제** 가능(`backend/requirements.txt`).
- **단계**:
  1. `backend/main.py`에 `@asynccontextmanager async def lifespan(app)` 작성, 엔진 로드를 `yield` 앞으로 이동.
  2. `app = FastAPI(lifespan=lifespan)`.
  3. `@app.on_event("startup")` 제거.
  4. `requirements.txt`의 starlette/fastapi 핀 해제 후 로컬 + Docker로 502 재현 없는지 확인.
- **검증**: `docker build` → `docker run` → `/api/ping`·`/api/chat` 정상. (CLAUDE.md "응답 안정성" 항목과 동일.)
- **위험**: 낮음. 단 핀 해제는 별도 커밋으로 분리(롤백 용이).

### B-6. 카드 데이터 단일 소스화 (핵심 — 세 목표 수렴)

- **무엇**: 카드 값의 **단일 진실원천(SSOT)** 을 `web/src/*.js`에서 **`data/standards.json`** 으로 분리. JS는 거기서 읽어 렌더, 백엔드는 그걸 서빙, diagnose·MCP가 당겨씀.
- **방향 결정(중요·열린 질문)** — 두 안 중 택1:
  - **(A) 추출(derive) 방식** ⭐ 권장: 현 JS 모듈을 SSOT로 유지하고, **`dump_cards.mjs` 확장으로 빌드시 `data/standards.json` 생성**. 장점: 기존 큐레이션·함수(relax/gg/green) 그대로, 회귀테스트 자산 재사용, 저위험. 단점: JS가 여전히 1차 소스(완전한 역전 아님).
  - **(B) 역전(invert) 방식**: `data/standards.json`을 1차 소스로 만들고 JS가 import. 장점: 진짜 SSOT, API·diagnose가 원본을 봄. 단점: incentive 함수 로직(relax/gg/green)을 데이터로 평탄화해야 → 표현력 손실·대공사·환각 위험.
  - **권장 경로: (A)로 시작** — `standards.json`을 **생성물(generated artifact)** 로 두고 git 추적. 사람은 계속 JS를 편집, 빌드가 JSON 동기화. 추후 (B) 전환이 필요해지면 그때.
- **단계 (A안 기준)**:
  1. `dump_cards.mjs`(또는 신규 `gen_standards.mjs`)가 6개 도메인 전부를 평가 → 통합 스키마로 `data/standards.json` 기록.
  2. 스키마(초안):
     ```jsonc
     {
       "built_at": "2026-06-30",
       "national": { "zone_defs": [ { "key": "1jeon", "bcrNat": 50, "farNat": 100, ... } ], "sunlight_rule": "..." },
       "domains": {
         "zoning":   { "regions": { "11": { "name": "서울특별시", "refs": ["..."], "rows": [ ... ] }, ... } },
         "parking":  { "regions": { ... } },
         "setback":  { ... }, "landscape": { ... }, "incentive": { ... }, "review": { ... }
       }
     }
     ```
     - region key = `code`. 각 region에 `refs`(근거 조문 id) 보존 → API 응답이 추적가능성 유지.
     - `src` 태그(manual/machine/llm, C-2)도 함께 직렬화 → API 소비자가 신뢰도 판단.
  3. **회귀 게이트 연결**: `standards.json` 생성을 pytest/`refresh_local.ps1`에 편입(카드 값 드리프트 시 JSON도 같이 검출). 골든은 이미 있음.
  4. 빌드 산출물이므로 `data/standards.json`을 Docker `data/` 복사에 포함(이미 `data/` 통째 복사 → 자동).
- **검증**: 생성된 `standards.json`의 zoning/landscape 값이 골든과 일치. 6개 도메인 region 수 = 카드 커버리지(용도지역 84·조경 80·주차 66·이격 77·심의 77·완화 82)와 대조.
- **위험**: 중간. incentive 함수 평가가 node 환경 의존 → `dump_cards.mjs`가 이미 처리하므로 재사용으로 흡수.

### B-5. 구조화 조회 엔드포인트 확장 (API 표면)

B-6 완료 후. 세 엔드포인트, 전부 **이미 로드된 graph/standards에서 읽기**(신규 fetch 0).

1. **`GET /api/article/{id}`** — 조문 메타 + 본문 + 시행일(`ef_yd`).
   - 소스: `rag_engine._by_id[id]`. 없으면 404.
   - 응답: `{ id, law_nm, title, content, ef_yd, category, url }`.
2. **`GET /api/citations/{id}`** — 인용/피인용.
   - 소스: graph의 `outRel`/`inRel`(또는 엣지 역색인). type별(references·cross_law·byeolpyo·delegates·applied·interpreted) 구분.
   - 응답: `{ id, out: [{id,title,type}], in: [{id,title,type}] }`.
   - D-8/D-9(Reader의 RelLegend·ImpactTree)가 쓰는 관계 데이터를 API로 노출하는 것 = 클라이언트 전용 로직의 서버화.
3. **`GET /api/standard?city=&zone=`** (또는 `?code=&domain=`) — 카드 데이터를 API로.
   - 소스: `data/standards.json`(B-6 산출물).
   - 응답: 해당 도시·용도지역의 국가 vs 도시 기준 + refs. **diagnose가 전국 비교를 graph에서 당겨쓰는 핵심 엔드포인트.**
   - 파라미터 설계 결정 필요: 도메인별 키가 다름(zoning=zone, parking=건물용도, landscape=연면적). → `/api/standard/{domain}?code=` 형태로 도메인을 경로에 두는 게 깔끔.
- **공통**: 읽기 전용 GET, `lookup`처럼 과도요청 방어(배치 상한), CORS는 현 nginx 설정 확인.
- **검증**: diagnose에서 실제 호출해 카드 값 일치 확인(E-12에서 검증된 참조 id 재사용 가능).

---

## 3. 실행 순서 · 검증 게이트

```
B-7 (lifespan, 독립·가벼움)
  └─ 커밋1: lifespan 이전 / 커밋2: 핀 해제
B-6 (standards.json 단일소스화)  ← 핵심
  └─ dump_cards.mjs 확장 → data/standards.json + 회귀 게이트 편입
B-5 (엔드포인트 3종)             ← B-6 산출물 의존
  ├─ /api/article/{id}
  ├─ /api/citations/{id}
  └─ /api/standard/{domain}?code=   ← diagnose 통합의 실제 진입점
```

- **상시 게이트**: `pytest`(카드 회귀 9검사) + GitHub Actions `test.yml`. 카드 값·`standards.json` 변경은 골든 승인(`--update-golden`) 거쳐야.
- **배포**: 각 단계 Cloud Run 자동 재배포. `ANTHROPIC_API_KEY`·`VOYAGE_API_KEY` 환경변수 유지 확인.

---

## 4. 열린 결정 포인트 (착수 전 사용자 확인)

1. **B-6 방식**: (A) 추출/생성물 ⭐권장 vs (B) JSON 1차소스 역전. → 권장 (A).
2. **`/api/standard` URL 설계**: `/api/standard/{domain}?code=` vs `/api/standard?domain=&code=`. → 권장 경로형.
3. **B-7 핀 해제 범위**: starlette만 vs fastapi 동반 업그레이드. → 최소 변경(starlette 핀만) 우선.
4. **착수 순서**: B-7부터(빠른 성취) vs B-6부터(핵심). → 권장 B-7 워밍업 후 B-6.

---

## 5. 비범위 (명시적 제외 — 환각·범위확장 방지)

- 산정 엔진·대지 GIS 탐지 — **diagnose 담당**. graph는 대지 컨텍스트 없어 무의미.
- 외부 법 API 신규 연동 — B는 *제공자*가 되는 것이지 *소비자*가 아니다.
- 카드 값 자체의 신규 추출·정확도 개선 — C그룹(완료) 영역.
- 실제 MCP 서버 구현 — B-6/B-5가 **전조**(추출기·데이터 분리)이며, MCP 서버화는 별도 후속(메모리 `mcp_serverization_goal`).
