# arch-law-graph — Claude 컨텍스트

건축 법령 관계 그래프 탐색기 + AI 자연어 질의.
법제처 DRF API → `data/graph.json` → React/Vite SPA + FastAPI 백엔드.
실무자(건축설계 소장·중간관리자)가 **건축 법령군(19개)을 주제별·피인용 순으로 빠르게 탐색**하고, **기준 조회**(용도지역·용도·규모별 건폐율·용적률·일조·주차·이격·조경을 국가 vs 도시로 즉답, 모두 근거 조문에 추적 가능)하며, **자연어 질의**(Claude RAG)로 복합 법령 해석을 얻는 게 핵심 목적.

---

## 프로젝트 구조

```text
builder/          # Python — 법제처 fetch → graph.json 빌드
  build_graph.py  # 법령 + 고시 + 조례(ordin_group) + 판례 + 해석례 전체 빌드. --only 건축법 가능
  ordin_group.py  # 전국 84시 + 82군 조례 목록(ORDIN_GROUP). inventory_ordin.py 자동생성, build_graph가 import
  inventory_ordin.py  # 전국 시·군 × 4조례를 법제처 API로 자동 검색·매칭 → ordin_group.py 생성(병목① 해소). CITIES+COUNTIES, 군 용도지역은 COUNTY_PLAN_CANON
  extract_zoning.py / extract_landscape.py  # graph 본문 정규식 추출(건폐율·용적률 / 조경). 손큐레이션 대조 검증
  gen_card_data.py  # 위 추출기 → zoning_auto.js·landscape_auto.js 생성(신규 도시, 기계적·무해석)
  gen_parking_llm.py / gen_setback_llm.py / gen_review_llm.py / gen_incentive_llm.py
                  # graph 별표/조문 → Claude(temp0) 스키마추출 → *_auto.js (주차·이격·심의·완화)
  build_embeddings.py  # 조문 → Voyage 임베딩 → data/embeddings.npy (벡터 RAG용, graph 갱신 시 재실행)
  law_go_kr_client.py  # 법제처 DRF 클라이언트 (law/admrul/ordin/prec/expc, 별표 + HWP 폴백)
  fetch_test.py   # 빠른 fetch 검증
  requirements.txt

backend/          # Python — FastAPI 자연어 질의 API (런타임)
  __init__.py
  main.py         # FastAPI app — /api/ping, /api/chat (SSE 스트리밍), /api/zoning (주소→VWorld→용도지역), /api/lookup
  rag_engine.py   # RRF 하이브리드(벡터 top-30 + 키워드 top-30 → RRF k=60) → Claude API. 벡터 없으면 키워드 FTS 폴백. 도메인 핀(_PIN_RULES)으로 건폐율/용적률 국가 기준 쿼리에 시행령 제84·85조 고정 주입
  requirements.txt  # fastapi, uvicorn[standard], anthropic, python-dotenv, httpx(VWorld)

web/src/
  App.jsx            # 최상위 shell — SearchView 하나 감싸는 구조
  views/SearchView.jsx  # 메인 뷰 — 검색 모드 + 기준 조회 모드 토글 + 💬 채팅 버튼
  views/ChatPanel.jsx   # AI 자연어 질의 패널 (사이드 드로어, SSE 스트리밍, 인라인 ref 링크)
  views/ComplianceCard.jsx  # 용도지역 카드 (건폐율·용적률·일조)
  views/ParkingCard.jsx     # 주차 카드 (건물 용도별)
  views/SetbackCard.jsx     # 대지 공지(이격) 카드
  views/LandscapeCard.jsx   # 조경 카드 (연면적 규모별)
  views/IncentiveCard.jsx   # 완화·혜택 카드 (공개공지·부설주차 면제, 행별 국가 vs 도시)
  views/ReviewCard.jsx      # 건축위원회 심의 대상 체크리스트 (법정 심의 + 도시 조례 심의)
  zoning.js parking.js setback.js landscape.js incentive.js review.js  # 기존 17개 손큐레이션 기준 데이터
  *_auto.js (zoning/landscape/parking/setback/review/incentive)  # 신규 도시 자동생성(builder), 본 파일이 import+append
  incentive_helpers.js  # 완화 카드 공유 헬퍼(gg/green/relax/PARKING_EXEMPT) — incentive.js+incentive_auto.js 순환 import 회피
  lib/lawContent.jsx    # 별표 테이블 파서·렌더러, LawBody 컴포넌트
  data.js              # 공유 데이터. graph.json 을 ?url 에셋 + top-level await fetch 로 런타임 로드(번들 분리).
                       # internalLaws, articlesByLaw, nodeById, citeIn, maxCite, outRel, inRel,
                       # lawOf(), lawColor(), familyOf(), tier(), DOMAINS, domainCount, etc.
  App.css              # 노션/토스풍 화이트 테마. --accent: #3182f6
  vite.config.js       # /api → localhost:8001 프록시 (개발용)

scripts/
  refresh_local.ps1   # 로컬 자동갱신 (작업 스케줄러용): 빌드 → 변경 시 commit·push
data/graph.json   # 빌드 산출물. git 추적(?url 정적 에셋으로 런타임 fetch)
data/embeddings.npy + embeddings_meta.json  # 조문 임베딩(Voyage, 벡터 RAG). git 추적, Docker가 data/ 복사
.github/
  workflows/refresh.yml         # GH Actions 크론 — 비활성화됨(법제처 IP 차단). 수동 dispatch만.
  scripts/graph_hash.py         # built_at 제외 MD5 해시 — 변경 감지용
Dockerfile        # multistage: node:20-alpine 빌드 → python:3.12-slim + nginx 런타임
startup.sh        # Docker CMD: uvicorn(8001) + nginx(8080) 동시 실행
nginx.conf        # port 8080, gzip, /api/ → uvicorn 프록시(SSE buffering off), SPA fallback
```

---

## 현재 상태 (2026-06-30 기준)

- **graph.json**: node≈42703, edge≈119911 — 법령 29 + 고시 17 + 조례 **554** + 대법원 판례 160 + 법령해석례 240 (Phase 1–4 + Stage 1–13 + E-10 완료. 판례·해석례 cap 100/150→160/240, build_graph.py `PREC_CAP`/`EXPC_CAP`)
  - 법령 29 = 건축 관련 법령 19 + **심의 별도 법령 5종(도시교통정비촉진법·환경영향평가법·경관법·지하안전관리에 관한 특별법·자연재해대책법) + 시행령 5종**(Stage 11).
  - 조례 554 = **전국 84개 시 + 82개 군 × 도시계획(군=군계획)·건축·주차·녹색건축 4종** + 경기도 도단위 2. 시 309 + 군 246(Stage 13). `builder/ordin_group.py`(자동생성)가 목록 보유, `build_graph.py`가 import.
    - **군(郡)은 검색·RAG·원문 corpus 전용** — 카드는 미생성(`gen_card_data.py`가 CITY_CODE=시만 처리). 군의 용도지역 조례명은 다양("○○군 도시계획/군계획/계획 조례") → `inventory_ordin.py`의 `COUNTY_PLAN_CANON` 접미사로 흡수. 광역시 산하 군(달성·군위·강화·옹진)은 자체 군계획 조례 없음(광역시 도시계획조례 적용). 청도군처럼 개정 꼬리표("[제명개정 …]") 붙은 조례명은 `clean_name()`으로 정규화(빌더 `search_ordin`도 동일 비교).
- **기준 조회(결정-등급 카드)**: 검색-퍼스트 외 `📐 기준 조회` 모드. 용도지역→건폐율·용적률·일조 / 건물용도→주차·이격 / 연면적→조경을 **국가 vs 도시 적용**으로 나란히 + 근거 조문 칩(클릭→원문 Reader) + 연결 판례·해석례 자동 수집. **전국 단위 카드(Stage 12).** 지역 스위처 = zoning REGIONS(마스터), 타 카드는 `r.code`로 조인(없으면 "준비중" guard). 카드별 커버리지:
  - **용도지역 84·조경 80** — 기계적 추출(정규식, 무료·무해석). 기존 17 손큐레이션 + 신규는 `zoning_auto.js`/`landscape_auto.js`(builder `gen_card_data.py` 생성, `?_auto.js` import+append).
  - **주차 66·이격 77·심의 77·완화 82** — LLM 보조 추출(claude-sonnet-4-6 temp0이 graph 별표/조문 → 스키마 JSON, 부산 등 손큐레이션 정확일치 검증). `parking_auto.js`·`setback_auto.js`·`review_auto.js`·`incentive_auto.js`(builder `gen_parking/setback/review/incentive_llm.py`). incentive 헬퍼는 `incentive_helpers.js`로 분리(순환 import 회피).
  - **충실성 원칙**: 모든 카드 값은 graph 원문 수치 그대로. 기계적 추출은 표기만 정규화(100분의 N·공백 이름·조사 생략·공장줄 제외). 소스 없는 도시·항목은 "준비중" guard(예: 원주 일반 조경, 수원 주차) — 지어내지 않음.
  - 코드 체계: 특·광역시·특별자치 = 2자리("11"서울), 기초시 = 5자리 법정동코드(`gen_card_data.py` CITY_CODE). 경기도는 도단위라 카드 미생성(조례는 graph에 두어 검색·RAG만).
- **번들 최적화(2026-06-29)**: graph.json(~58MB)을 `?url` 정적 에셋으로 분리 + `data.js` top-level await fetch → **JS 번들 7.3MB→110KB gzip(98.5%↓)**. graph는 별도 캐싱·JSON.parse. `vite.config.js` build.target es2022, `index.html` 로딩 스피너.
- **AI 자연어 질의(Stage 3 + C-3 + RRF 하이브리드)**: 오른쪽 하단 `💬` 버튼 → 사이드 드로어. **RRF 하이브리드 검색**(Voyage 벡터 top-30 + 키워드 top-30 → RRF k=60 → top-12) + **도메인 핀**(`_PIN_RULES`: 건폐율/용적률 + 국가·시행령·상위법 키워드 시 시행령 제84·85조 고정 포함) → Claude API SSE 스트리밍. 컨텍스트 max_chars=6000(시행령 제84조 5187자 완전 포함). 의미가 통하면 단어가 안 겹쳐도 매칭(예 "옆 건물과 얼마나 떨어뜨려야" → 대지 안의 공지). `VOYAGE_API_KEY`/`embeddings.npy` 없으면 키워드 FTS로 자동 폴백. 답변 내 `법령명 제N조` 패턴 자동 파싱 → 클릭 시 Reader 원문. selected_id 자동 컨텍스트 주입. 하단 근거 조문 칩 병행. **eval 결과**: `builder/eval_rag.py` 34문항 → 결론 일치 38%(키워드FTS) → 71%(RRF) → **88%(RRF+핀+chars)**, 법령 인용 97%.
- **HWP 별표 폴백**: 부산·인천 조례 별표는 본문이 HWP 첨부뿐(별표구분='서식'으로 표기). 빌더가 `별표첨부파일명` URL → 다운로드 → `pyhwp(hwp5html)` 변환 → HTML 표를 **선문자(박스드로잉) 텍스트**로 렌더해 graph.json 별표 content 채움. ⚠ `-m hwp5.hwp5html`는 Windows에서 빈 출력 → 콘솔 `.exe` 직접 호출.
- **법제처 API 접근**: 이 로컬 머신(국내 IP)에서 직접 작동 → 재빌드·조례 fetch 가능. GH Actions만 차단됨.
- **배포**: Cloud Run (GitHub push → 자동 재배포). Cloud Run 환경변수에 `ANTHROPIC_API_KEY` 설정 필요.
- **자동갱신**: 로컬 Windows 작업 스케줄러 "arch-law-graph 자동갱신" (매일 09:00, `scripts/refresh_local.ps1`). GitHub Actions 크론은 비활성화 — 법제처 API가 GH 러너(해외 IP)를 차단해 빈 결과 반환하기 때문.
- **빌드 venv**: `D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe` (networkx·httpx·dotenv·fastapi·anthropic 설치)
- **GitHub**: `https://github.com/DaDaDiRaRa/arch-law-graph`

### 법령군 (29개) — `builder/build_graph.py` LAW_GROUP

- 건축법 패밀리: 건축법/시행령/시행규칙 + 피난ㆍ방화구조 규칙·설비기준 규칙·구조기준 규칙·건축물대장 규칙
- 국토계획: 국토계획법/시행령/시행규칙
- 주차장법/시행령/시행규칙
- 건축물의 분양법/시행령/시행규칙
- 녹색건축물 조성 지원법/시행령/시행규칙
- 심의 별도 법령(Stage 11): 도시교통정비촉진법/시행령 · 환경영향평가법/시행령 · 경관법/시행령 · 지하안전관리에 관한 특별법/시행령 · 자연재해대책법/시행령

### 확장 로드맵 (실무 가치 순)

1. ✅ Phase 1 — 누락 위임 부령·하위법령 보강 (target=law, 완료 2026-06-25)
2. ✅ Phase 2 — 국토부 핵심 건축 고시 17개 (admrul, 완료 2026-06-25). 조문형식 아닌 고시는 장(章) blob, hwp 첨부뿐인 고시는 자동 스킵.
3. ✅ Phase 3 — 서울특별시 건축 조례 4종 (ordin, 완료 2026-06-25). 조문번호 6자리(조4+가지2)는 `_ordin_article_no`로 정규화.
4. ✅ Phase 4 — 대법원 판례 40 + 법령해석례 60 (prec/expc, 완료 2026-06-25). 참조조문에서 (법령명, 제N조) 추출 → `applied`/`interpreted` 엣지.
5. ✅ Stage 1 — 기준 조회(결정-등급 카드) 도입 (완료 2026-06-25).
6. ✅ Stage 2a — 서울 주차·이격·조경 카드 추가 (완료 2026-06-25).
7. ✅ Stage 2b — 멀티리전(부산·인천) 확장 (완료 2026-06-25). 조례 6종 + HWP 폴백.
8. ✅ Stage 3 — AI 자연어 질의 채팅 패널 (완료 2026-06-25). FastAPI RAG + Claude SSE + 인라인 ref 링크.
9. ✅ Stage 4 — 판례·해석례 확대(40→100, 60→150, 키워드 19개) + 조례 4개 광역시(대구·대전·광주·울산) 추가 (완료 2026-06-26). 용도지역(건폐율·용적률·일조)·조경 카드 7개시 지원. 주차·이격 카드는 서울·부산·인천만 → 나머지 도시는 "데이터 준비 중" guard.
10. ✅ Stage 5 — 조례 6개 지자체 추가(세종·제주·수원·용인·고양·창원) + 경기도(검색용) (완료 2026-06-26). 용도지역·조경 카드 13개 지자체로 확장. 창원 건폐율·용적률은 표 없는 HWP → 빌더 문단 텍스트 폴백으로 추출. 특례시 지자체기관명은 "경기도 수원시" 형식.
11. ✅ Stage 6 — 신규 도시 주차·이격 카드 큐레이션 (완료 2026-06-26). 주차 7개시(대구·울산·세종·용인·고양·창원·제주)·이격 7개시(대구·울산·세종·수원·용인·고양·창원) 추가 → 주차·이격 각 10개 지자체. 부설주차·대지안의공지 별표(HWP 박스표)에서 use-type별 추출. 대전·광주·제주(이격)·수원(주차)은 별표 데이터 미정비로 보류(guard).
12. ✅ Stage 7 — 보류 도시 마무리 (완료 2026-06-26). 빌더에 HWPX(zip/OWPML) 변환 + 일반제목("별표 N") 데이터표 변환 추가 → 대전·광주 주차, 대전·광주·제주 이격 별표 추출. 주차 12개·이격 13개 지자체. 수원 주차만 영구 보류(일반 주차장 설치 조례가 법제처 ordin DB에 없음 — 보훈시설 조례만 존재).
13. ✅ Stage 8 — 실무 토픽(완화·혜택) 카드. 새 `완화·혜택` 서브탭, 13개 지자체. graph에 이미 있는 조문에서 큐레이션(빌더 변경 없음).
    - Phase 1 ✅ (2026-06-26) — 공개공지(대상·면적·완화) + 부설주차 면제·완화.
    - Phase 2 ✅ (2026-06-26) — 용적률·건폐 완화 인센티브(공공기여·임대주택·사회복지 기부·방재/방화지구). 국토계획법 시행령 제84·85조 틀 + 도시 도시계획조례 완화 조문.
    - Phase 3 ✅ (2026-06-26) — 친환경(녹색건축·ZEB 인증등급별 완화·의무). **완화비율이 국토부 고시「건축물의 에너지절약설계기준」별표9로 전국 통일** → 완화율은 graph 기존 별표9·법 제15조·시행령 제11·12조 활용. 녹색건축 최우수 6%·우수 3% / ZEB 1~5등급 15~11% / 시범사업 10%.
    - Phase 3 보강 ✅ (2026-06-26) — 도시별 재정지원 차이 surface. 녹색건축물 조성 지원 조례 13개 fetch(ORDIN_GROUP) → `green()` 함수의 "재정 지원" row를 도시별로(그린리모델링 기금 보유: 부산·인천·대구·광주·제주 / 노후주택 지원금: 수원·고양·용인·창원 / 간소: 대전·세종). 완화율·세제는 전국 동일.
14. ✅ Stage 9 — 건축위원회 심의 대상 체크리스트 (완료 2026-06-26). 새 `심의 대상` 서브탭, 13개 지자체. 법정 심의(시행령 제5조의5①) + 도시 조례 심의(규모·용도·지역) + 기타 심의·평가·의무(안전영향평가·CPTED·에너지절약계획서·결로·해체) + 별도 법령 검토(교통·환경·경관·지하안전·재해, 참고). 광역시·특별시는 시·도/자치구 위원회 관할 분리(si/gu), 단일계층·일반시는 local. graph 기존 조문 큐레이션(빌더 변경 없음). `review.js`/`ReviewCard.jsx`.
15. ✅ Stage 10 — 조례 지자체 4개 추가(성남·청주·전주·천안) (완료 2026-06-26). 6개 JS 데이터 파일 큐레이션. 주차 12→16개·이격·용도지역·조경·완화혜택·심의 13→17개. 특이값: 청주·천안 아파트 이격 6m, 천안 중심상업 BCR 90%/FAR 1200%, 종합병원 이격 4m(규모 무관), 전주 조경 다단계, 천안 공개공지 6%/8%/10%.
16. ✅ Stage 11 — 심의 별도 법령 정밀화 (완료 2026-06-26). 도시교통정비촉진법·환경영향평가법·경관법·지하안전관리에 관한 특별법·자연재해대책법 + 각 시행령 10개 법령 graph 추가(node 6595→8936). `REVIEW_CROSSLAW`를 `{label, basis, threshold, refs[]}` 구조로 전환, 정확한 규모 임계값 + 근거 조문 칩(liveRefs filter). 소규모 지하안전평가 제23조(제25조 오기 수정), 경관 제27조(개발사업) 추가, refs 13개 전량 graph 실재 검증.
17. ✅ **Stage 12 — 전국 84개 시 확장** (완료 2026-06-29). 17→84개 시.
    - **병목① 자동 해소**: `inventory_ordin.py`가 전국 시 × 4조례를 법제처 API로 자동 검색·매칭(주차는 표준접미사 화이트리스트로 부속조례 배제) → `ordin_group.py`(309조례). build_graph가 import. 재빌드 node 8936→24800.
    - **기계적 카드(무해석)**: 건폐율·용적률·조경이 본문 번호목록이라 정규식 추출 가능 → 용도지역 84·조경 80개. 표기 정규화(100분의 N·공백 이름·조사생략·공장줄 제외)로 충실 추출, 소스 없으면 guard.
    - **LLM 보조 카드**: 주차·이격·완화·심의는 별표 표/산문 → Claude(temp0) 스키마추출. 초기 주차 65·이격 64·심의 46·완화 82. 부산 등 손큐레이션 정확일치로 환각 없음 검증. 별표 원문 수치만 사용.
    - **번들 최적화**: graph.json `?url` 분리 + TLA fetch → JS 번들 7.3MB→110KB gzip.
    - **HWP 게이트 보강(2026-06-29)**: `_BP_TABLE_TITLE`에 `공지|주차|이격|조경` 신호 추가 + `_BP_BUNDLE_TITLE`(묶음 범위 제목) 인식 + `_split_box_tables()`/`_classify_byeolpyo_table()` 추가 → 화성·의정부·광주·목포 등 이격 별표 신규 확보. 재빌드 node 24800→25235, 이격 64→77·주차 65→66. 심의도 gen_review_llm.py 재실행으로 46→77.

### 노드 category 체계

법령(없음)·고시(`고시`)·조례(`조례`)·판례(`판례`)·해석례(`해석례`). data.js 의 lawColor/familyOf 가 색상·라벨 분기. 판례/해석례→조문 엣지(applied/interpreted)는 조문의 '피인용'(citeIn/inRel)에 집계됨.

---

## 핵심 아키텍처 결정

### 데이터 흐름

```text
법제처 DRF API → build_graph.py → data/graph.json
                                        ↓ (vite ?url 정적 에셋 — JS 번들 미포함, 런타임 fetch)
                              nginx 정적 서빙 (Cloud Run :8080)

사용자 자연어 질문
  → /api/chat (nginx → uvicorn :8001)
  → rag_engine: 질의 Voyage 임베딩 → embeddings.npy 코사인 top_k=12 (폴백: 키워드 FTS)
  → Claude API (claude-sonnet-4-6, streaming)
  → SSE 스트리밍 응답 → ChatPanel 인라인 ref 렌더링
```

**런타임 호출**: Anthropic Claude API(`ANTHROPIC_API_KEY`) + Voyage 임베딩(`VOYAGE_API_KEY`, 질의당 1회·미설정 시 키워드 폴백). 법제처 API는 빌드 시에만.

### UI — 3가지 모드

1. **🔍 검색**: 조문 번호/제목/본문 풀텍스트. 검색 문법: `"정확한 구절"`, `-제외어`, AND(스페이스). 결과 정렬: 피인용 수 내림차순. 별표 인라인 렌더링, ★ 북마크, 도메인 칩 필터.
2. **📐 기준 조회**: 용도지역/건물용도/연면적 선택 → 국가 vs 도시 기준 카드. 근거 조문 칩 클릭 → Reader. **상단 주소 입력창**(`/api/zoning`) → VWorld로 용도지역 자동 조회 → REGIONS 매칭(sido/sigungu↔r.name) + zone 자동 선택 → 카드 즉시 렌더.
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

# ── 조문 임베딩 사전계산 (벡터 RAG, graph 갱신 후 재실행 권장. VOYAGE_API_KEY 필요) ──
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder/build_embeddings.py

# ── 카드 회귀 스냅샷 테스트 (C-1). 루트에서 실행 ──────────────────────────
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe -m pytest        # 11검사: zoning/landscape × (frozen·extractor_sync·plausible) + LLM카드(주차·이격·심의·완화) × (frozen·structural·plausible) + standards.json × (sync·structural, B-6). node 필요(LLM카드·standards 평가)
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe -m pytest --update-golden  # 카드 값 변경을 사람이 승인(골든 재생성)

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
VOYAGE_API_KEY=...       # 벡터 RAG 임베딩 (빌드 build_embeddings.py + 런타임 질의). 없으면 키워드 FTS 폴백
VOYAGE_MODEL=...         # 선택, 기본값 voyage-3-large.  VOYAGE_DIM 기본 1024
VWORLD_API_KEY=...       # 주소→용도지역 자동조회 (/api/zoning 런타임). 미설정 시 입력창에 안내 에러
SERVICE_URL=...          # VWorld 데이터 API Referer (기본 http://localhost:8000). Cloud Run은 등록 도메인 설정 필수
```

**Docker/Cloud Run**: `.env`는 `.dockerignore`에 의해 컨테이너 미포함.
`ANTHROPIC_API_KEY`·`VOYAGE_API_KEY`는 반드시 Cloud Run 환경변수(GCP Console → 새 버전 수정 및 배포 → 변수 및 보안 비밀)에 별도 설정. VOYAGE 미설정 시 컨테이너는 자동으로 키워드 FTS로 동작(에러 X). `data/embeddings.npy`는 Dockerfile이 `data/` 복사 시 자동 포함.

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
| 대전·광주 주차 조례명 불일치(`주차장 조례`) | ORDIN_GROUP에 정확명 등재(다른 도시는 `주차장 설치 및 관리 조례`) |
| 울산 도시계획 별표24(건폐율·용적률) 빈 값 | `_BP_TABLE_TITLE` 신호에 `건폐율`·`용적률` 추가 → HWP 변환 |
| 신규 도시 주차·이격 데이터 미보유 시 카드 크래시 | SearchView `pkRegion`/`sbRegion` undefined guard("데이터 준비 중") |
| 광주·제주 별표가 HWPX(zip)라 pyhwp 변환 실패 | `_tables_from_hwpx`(zip→`hp:tbl` 파싱) 추가, `PK` 헤더면 HWPX 경로로 분기 |
| 대전·광주 데이터표 별표 제목이 일반("별표")이라 신호 미통과 | 변환 게이트에 일반 제목(`^\[?별표 N\]?`) 허용(별지=표지판 제외) |
| 특례시 조례 검색 실패 | 지자체기관명이 "경기도 수원시" 형식 — ORDIN_GROUP에 (그 형식, "수원시 ○○ 조례") 등재 |
| 창원 별표27/28(건폐율·용적률) HWP에 표 없음 → 빈 값 | `_hwp_bytes_to_box_text`에 표 없을 때 `_text_from_xhtml` 문단 텍스트 폴백 추가 |
| 도시 탭 13개로 가로 넘침 | `.region-switch`에 `flex-wrap: wrap` |
| 조례명·기관명 수동 추측(도시당 시행착오) | `inventory_ordin.py`가 전국 자동 매칭 → `ordin_group.py` 생성 |
| graph.json 53MB가 JS에 인라인 → 번들 7.3MB gzip | `?url` 에셋 분리 + `data.js` top-level await fetch → JS 102KB gzip |
| TLA 빌드 실패 | `vite.config.js` build.target `es2022` |
| 용도지역 파싱 0/부분(군포·과천 등) | `100분의 N` 분수표기 인식 + 공백 무시 매칭(과천 "제1종 전용주거지역") |
| 조경 파싱 누락(포천·양산·원주) | "의" 조사 선택적 + `100분의 N`(퍼센트 없는 분수) + 공장줄 일반tier 제외 |
| incentive_auto import만 하고 spread 누락 → 완화 미반영 | `...BENEFIT_AUTO` 배열 추가(빌드는 통과해 시각확인서 발견) |
| HWP 별표 게이트가 `공지\|주차` 신호 누락 → 이격·주차 별표 미fetch | `_BP_TABLE_TITLE`에 `공지\|주차\|이격\|조경` 추가 → 이격 64→77, 주차 65→66 |
| 묶음 HWP("[별표 1]~[별표 N]") 제목이 게이트 미통과 → 전체 스킵 | `_BP_BUNDLE_TITLE` + `_split_box_tables()` + `_classify_byeolpyo_table()` 추가, 묶음 분할 후 개별 표 판별 |
| RAG 벡터 검색이 조례 조문에 밀려 국가법(시행령 제84조) 미반환 → "DB 확인 불가" hedging | RRF 하이브리드(벡터+키워드 융합) + 도메인 핀(`_PIN_RULES`) + max_chars 1500→6000 → 결론 일치 38%→88% (`builder/eval_rag.py`) |
| VWorld 데이터 API(GetFeature)가 같은 키로 `INCORRECT_KEY` (address API는 OK) | 데이터 API는 키 발급 시 등록 도메인의 **`Referer` 헤더** 검사 → `Referer: SERVICE_URL`(기본 `http://localhost:8000`). Cloud Run은 등록 도메인으로 SERVICE_URL 설정 필요 |
| VWorld 용도지역 속성명 `UQ_NM`로 추측 → 빈 값 | LT_C_UQ111 실제 속성명은 **`uname`**(자매앱 arch-law-diagnose `vworld_client.py` 검증) |
| 추출기가 `100분의 1,000`(천단위 쉼표)을 `100분의1`=1% 로 오파싱 → 군포 중심상업 용적률 1% garbage가 zoning_auto.js 에 배포됨 | `extract_zoning.py` val 정규식 `100분의\d+`→`100분의\d[\d,]*`. **카드 회귀 테스트(C-1)의 타당성 경계가 검출**(용적률 허용 50~1500) |
| 주소 자동조회에서 카드 미지원 지역(군 등) 입력 시 매칭 실패해도 현재 선택 도시(기본 서울) 카드를 그대로 표시 → 군 땅을 서울 기준으로 오인 | `SearchView.jsx handleAddrSearch`: `matched` 없으면 카드 변경 없이 "시 단위 카드 미지원(용도지역만 확인)" 안내 후 return. 군은 graph corpus에 0(시 83만) — 위임주체 검증: 건폐율·용적률=시·군(구 제외), 주차=시·군·구(주차장법§19). 자치구 도시계획/주차 조례 실재 확인(강남구) |

---

## 다음 작업 후보

### 정체성 (방향타) — diagnose와의 역할 분담

자매앱 **arch-law-diagnose**(`D:\APPS\arch-law-diagnose`)가 "이 대지에 지을 수 있나"(대지 GIS·산정 계산·신호등·사업성)를 가져감. 따라서 graph = **건축 법령의 단일 권위 지식원**. 네 단어: **권위(전체 법령군)·추적가능(원문 근거)·최신(시행일)·호출가능(법령 API)**.

- 소비자 셋: ① 사람(웹 검색·Reader), ② RAG 채팅(**법령 해석** Q&A — 진단 Q&A 아님), ③ 기계/타앱(diagnose·미래 MCP).
- 표어: **"이 법이 뭐라고 하는가, 어디 근거하며, 무엇과 연결되는가."**
- **graph는 산정·대지탐지를 구현하지 않음**(diagnose 담당). 단 그 계산의 *근거 조문 원문*은 graph가 보유(diagnose RAG가 `/api/lookup`으로 당겨씀). 통합 웹사이트 시 중복 기능(AI채팅·법규그래프 뷰)은 주인을 하나로 명시.

> **검증된 현재 상태(2026-06-30 코드 확인)**: API 표면 = `/api/ping`·`/api/zoning`·`/api/lookup`(배치 50)·`/api/chat` + **B-5 신규** `/api/article/{id}`·`/api/citations/{id}`·`/api/standard/{domain}?code=` (총 7개, 전부 읽기 전용·재빌드 0). `ef_yd`(조문시행일자)는 **중앙법령 조문에만** 저장(article 37867 중 2134; 조례·고시·판례·해석례는 미저장)·Reader+카드 근거칩+RAG 인용칩+`/api/article`에 `2026-03-24` 형식으로 전파됨(C-3 완료 2026-06-30, `fmtEf`/`efDate`/`RefChip`). 빌더가 `현행연혁구분!=현행` 필터 → **현행 법령만** 보유(연혁 타임라인 없음). **카드 회귀 테스트 11건**(C-1+Opt3+B-6, 2026-06-30 — zoning/landscape × frozen·extractor_sync·plausible + LLM카드(주차·이격·심의·완화) × frozen·structural·plausible + standards.json × sync·structural; GitHub Actions CI(`test.yml`) push·PR 실행; diagnose는 262건). **카드 데이터는 `data/standards.json`으로 단일소스화돼 API·diagnose가 당겨씀**(B-6 완료, JS는 1차소스 유지·JSON은 생성물).

### 우선순위 로드맵 (정확도 + 정체성 기준)

#### C. 정확도·신뢰 — 최우선 (graph가 데이터 주인)

- ✅ **1. 카드 추출 회귀 스냅샷 테스트** (완료 2026-06-29) — `pytest`(루트, `pytest.ini`→`builder/tests/`). zoning 84·landscape 80개 시를 골든 스냅샷(`builder/tests/golden/*.json`, 값별 `src` 태그 extracted/hwp/manual/auto)에 고정. 카드당 3검사: **frozen**(live==골든, 사람 미승인 변경 차단)·**extractor_sync**(추출기 재실행==커밋카드, 재빌드/추출기수정 드리프트 검출)·**plausible**(건폐율 20~90·용적률 50~1500·조경 3~30 경계로 garbage 검출). `refresh_local.ps1`이 자동갱신 시 게이트로 실행 → 카드 값 바뀌면 자동 커밋 차단. 골든 승인은 `pytest --update-golden`. **버그 적발 실적**: 군포 중심상업 용적률 1%(쉼표 오파싱) garbage를 plausible이 검출 → 추출기 수정.
  - ✅ **Opt3 확장**(완료 2026-06-30) — LLM 카드(주차·이격·심의·완화) **frozen 동결**(`test_llm_cards.py`). LLM 출력이라 재현 불가 → extractor_sync 대신 frozen+structural+plausible. incentive items 가 함수 호출(relax/gg/green)이라 `dump_cards.mjs`(node)로 실제 평가 후 골든(`cards_llm.json`) 대조. **GitHub Actions CI**(`.github/workflows/test.yml`) push·PR 마다 pytest 실행(커밋된 graph.json+JS만 읽어 법제처 불필요, node 셋업). 카드 모듈 상대경로 import만 써 npm install 불요. 다음: 출처 배지(C-2).
- ✅ **2. 값별 출처·신뢰도 배지** (완료 2026-06-30) — 6개 카드 데이터 모듈에 `src` 태깅(손큐레이션=manual·기계추출=machine·LLM보조=llm). 태깅은 export 스프레드에서 `...AUTO.map(r=>({...r,src})).` + `].map(r=>({src:"manual",...r}))`(손큐는 미지정→manual, AUTO는 자체 src 유지). `web/src/views/SourceBadge.jsx` 가 카드 cc-head 의 도시명 옆에 색상 배지+툴팁 렌더(6개 카드 전부). LLM 카드 골든(`cards_llm.json`)에 src 포함돼 frozen 테스트가 태깅 변경도 감시. guard "준비중"은 기존 빈-상태로 표시.
- ✅ **3. 시행일 전파** (완료 2026-06-30) — `ef_yd`를 Reader(포맷 `2026-03-24`)·카드 근거 조문 칩·RAG 인용칩(하단 출처칩 가시 + 인라인 ref 툴팁)에 전파. 공유 헬퍼 `fmtEf`/`efDate`(data.js) + 공유 컴포넌트 `views/RefChip.jsx`(6개 카드 칩 중복 제거, `.cc-ef` CSS). ⚠ **ef_yd는 중앙법령(법령 29종) 조문에만 존재**(article 37867 중 2134) — 조례·고시·판례·해석례 조문은 빌더가 시행일 미저장 → 해당 칩은 라벨만(graceful degrade). 건폐율·용적률(시행령 제84·85조)·주차·이격(시행령 별표) 등 국가기준 칩은 날짜 표시됨. 조례 시행일까지 보장하려면 빌더에 조례 `시행일자` 저장 + 재빌드 필요(후속·선택).
- ✅ **4. RAG 인용 검증 라이트** (완료 2026-06-30) — `rag_engine.verify_citations()`가 답변 본문의 `법령명 제N조`(가지번호 포함) 인용을 사후 파싱해 graph 실재 여부 확인. **보수적**: 실재 법령명(본문 가진 article의 law_nm, 841개·긴이름우선)이 제N조 바로 앞에 올 때만 검증 → 해당 조문 노드 부재 시 unverified. 대명사("동법 제5조")·도시접두어 없는 조례("도시계획 조례 제44조" — phantom)·무공백명은 anchor 안 됨(오탐 0 검증). `answer_stream`이 토큰 누적→검증→`done` 이벤트에 `unverified[]` 동봉, ChatPanel이 답변 하단 호박색 경고(`.chat-unverified`) 렌더. 임베딩·재빌드 불필요(순수 사후처리). **잘못된 법령명 anchor 주의**: phantom law 노드(인용추출 산물, 본문無)를 article-law-set으로 배제하는 게 정확도 핵심.

#### B. 법령 API / 호출가능성 — ✅ 완료 (2026-06-30, 고유 역할 + 통합·MCP 전조)

> ⚠ "법령 API" = graph가 **제공자(서버)** 가 되는 것. **외부 법 API를 새로 붙이는 게 아니라**, 이미 가진 graph.json을 엔드포인트로 노출. 소스는 법제처 하나로 충분(권위는 소스 수가 아니라 *건축 법령 내 깊이*에서 나옴). diagnose의 VWorld/EUM/LURIS는 대지 데이터라 graph가 끌어오지 않음.
> 목적: **앱 통합 + 호출가능성**(정확도 아님=C그룹). 웹앱 동작은 불변(순수 추가). 상세 계획 `doc/B-law-api-plan.md`.

- ✅ **5. 구조화 조회 엔드포인트 확장** (완료) — `GET /api/article/{id:path}`(메타+본문+시행일 ef_yd)·`GET /api/citations/{id:path}`(인용 out/피인용 in, contains 제외·type별)·`GET /api/standard/{domain}?code=`(카드 데이터를 API로 → diagnose가 전국 비교를 graph에서 당겨씀). 전부 이미 로드된 graph/standards에서 읽기(신규 fetch·재빌드 0). 엔진에 `_out_rel`/`_in_rel` 엣지 인덱스(프론트 outRel/inRel 동일 의미론) + `get_article`/`get_citations` 추가. id 슬래시 포함 → `{id:path}` 컨버터. nginx `/api/` 프록시·CORS GET 기존 설정 그대로.
- ✅ **6. 카드 데이터 단일 소스화** (완료) — `builder/gen_standards.mjs`가 6개 카드 JS(`web/src/*.js`)를 Node로 평가 → `data/standards.json`(생성물, git 추적, ~1.5MB). **(A) 추출 방식**: JS가 여전히 1차 소스(SSOT), JSON은 동기화 산출물 → 웹앱 동작 불변. incentive 함수(relax/gg/green)는 Node 평가로 정적화. 회귀 게이트 `test_standards_sync.py`(node `--stdout` 재평가 == 커밋본, +structural). Docker `data/` 복사로 자동 포함. **한 작업이 API·MCP·통합 세 목표로 수렴.** ⚠ 카드 JS 수정 시 `node builder/gen_standards.mjs` 재실행 필요(미실행 시 sync 테스트 실패).
- ✅ **7. 응답 안정성** (완료) — `@app.on_event("startup")`(deprecated) → `lifespan` 컨텍스트 핸들러로 이전(`backend/main.py`). on_event 의존 제거 → starlette/fastapi 핀의 *사유*(과거 502) 해소. 핀 자체는 재현성 위해 유지(주석만 갱신, 무검증 업그레이드 회피).
- (후속·선택) **카드 1차소스 역전(B안)·실제 MCP 서버 구현** — B-6이 전조. 필요해지면 착수.

#### D. 관계 그래프 심화 — 높음 (graph라는 *이름값*, diagnose 불가 영역)

- ✅ **8. 엣지 타입 구분 노출** (완료 2026-06-30) — Reader에 `RelLegend`(관계 타입 범례+단일 필터). 색은 이미 `REL_COLOR`로 있었음 → 범례(참조·타법령·별표·**위임**·판례·해석례)+타입별 카운트+클릭 필터 추가. `relFilter` state가 CiteGraph·RelCol 양쪽 list를 필터링 → 희소관계(위임 20개 등)를 끊어 봄. 데이터는 `outRel/inRel`의 type 재활용(빌더·백엔드 변경 0). `web/src/views/SearchView.jsx`+App.css.
- ✅ **9. 경로·영향 분석** (완료 2026-06-30, 영향 트리) — Reader에 `ImpactTree`(접이식). 현재 조문의 **피인용 전이폐쇄**(`inRel` 역방향 BFS, 깊이3·총량cap80, visited 최단깊이1회·사이클가드)를 깊이별(1단계 직접·2~3단계 간접)로 노출 = "이 조문 개정 시 영향받는 조문 트리". 실측: 시행령 제84조 direct7→transitive28[7,5,16], 주차장법 제19조[11,9,6]. 클라이언트 전용(BFS 순수 JS). ⚠ 잔여(미구현): "조문 A→B 최단경로"(타깃 picker UX 필요)는 보류 — 영향트리가 핵심 가치라 우선.

#### E. 데이터 폭 — 중간 (권위 corpus 강화)

- ✅ **10. 판례·해석례 확대** (완료, E-10) — cap 100/150→**160/240**(build_graph.py `PREC_CAP`/`EXPC_CAP`), 키워드 보강(완화·심의·친환경 등). graph 실측: 판례 노드 151·해석례 240, applied 313·interpreted 2160 엣지.
- ✅ **11. 군(郡) 지역 조례** (완료 2026-06-30, Stage 13) — 82개 군 추가(조례 309→554, node 25235→42405). 검색·RAG·원문 corpus(카드 미생성). 도 산하 군 전원 용도지역 조례 확보, 광역시 산하 4군은 광역시 조례 적용. 카드 회귀 게이트가 시 값 불변 확증. 임베딩 재계산 완료(`embeddings.npy` 17928→30784, 군 벡터 RAG 검증). **잔존**: graph.json 58→93MB·embeddings 37→63MB(서버 에셋). 클라이언트 graph 12.6MB gzip 첫 로드 — 모바일 체감 나빠지면 서버사이드 검색(B-5)으로 근본 해결.
- ✅ **12. diagnose 인용 조문 보유 확인** (완료 2026-06-30) — diagnose `law_graph_auto.json`+`law_graph_seed.json`의 참조 조문 127개를 graph 실재성 검사(법령명 약칭·별표·가지번호 정규화 + 실제 `lookup()` 통과). **결과: graph corpus 빈틈 0 — 빌더 보강 불필요**. 분류: OK 72 / 19법령군 밖 EXTERNAL 48(용도분류·심의 외부법령, 정체성상 정상·degrade) / ARTICLE GAP 7. **7건 전부 diagnose 측 오류**(법제처 현행 fetch로 확정 — 4건은 法/시행령 오기재: 건축법 제13의2·53의2·77의2·77의4가 graph에 `건축법` 본문으로 실재하나 diagnose가 `건축법 시행령`으로 참조 / 3건은 현행 미존재 조문번호: 건축법 제7의2·주차장법 제51·녹색건축법 제61). 빌더 fetch 조문수가 graph와 정확 일치(건축법166·시행령203·녹색46·주차71)로 빌더 완전성도 교차확인. **후속(graph 무관, diagnose 숙제)**: diagnose가 7개 참조 수정.
- **14. (선택·advanced) 개정 진행중(입법예고) 추적** — 법제처 DRF는 **현행 법령만** 제공(빌더가 `현행연혁구분!=현행` 버림) → graph는 "곧 시행될 개정"을 모름. "최신" 정체성을 날카롭게 하는 **유일한 정당한 외부 소스 추가**(국회 의안정보시스템·법제처 입법예고). 실무가치: "준공 시점엔 바뀐 법 적용". ⚠ 난도·유지보수 있어 1·6번보다 후순위.

#### A. 정체성·UX 정리 — 낮음(저비용)

- **13. 카드 = "전국 비교 레퍼런스" 리프레이밍** — 라벨·문구에서 "진단" 뉘앙스 제거, "대지별 판정은 diagnose" 안내.

### 명시적 제외 (환각·과장 방지)

- **산정 엔진·대지 GIS 탐지** — diagnose 담당. graph는 대지 컨텍스트 없어 무의미.
- **3D 우주 시각화(galaxy 류)** — 실무 ROI 낮음. 이름값은 *관계의 깊이*(D)로 내지 화려함으로 내지 않음.
- **RAG eval 88→95% 추격** — 수확체감(복합추론·모델 한계). 4번(인용 검증)으로 *틀린 답 차단*에 집중.
- **연혁 타임라인** — "현행이 무엇인가"는 시행일로 충분. 특정 수요 생기면 그때.
- **진단 종합 리포트/Excel** — diagnose 산출물 영역.

### 운영·배포 (상시)

- **Cloud Run 배포** — GitHub push → 자동 재배포. ⚠ `ANTHROPIC_API_KEY`가 Cloud Run 환경변수에 설정돼야 AI 채팅 작동.
- **데이터 자동갱신** — 로컬 작업 스케줄러(매일 09:00, `scripts/refresh_local.ps1`). ⚠ 신규 조례는 `ordin_group.py`에 있어야 추적 — 새 지자체는 `inventory_ordin.py` 재실행.

### 완료 이력

- ✅ **B. 데이터** — 조례 전국 84개 시(Stage 12) + 82개 군(Stage 13, 조례 554) + 판례·해석례 확대(E-10) → node 42703.
- ✅ **카드 회귀 스냅샷 테스트(C-1+Opt3+B-6)** — `pytest` 11검사(zoning/landscape × frozen·extractor_sync·plausible + LLM카드 × frozen·structural·plausible + standards.json × sync·structural) + 골든 + refresh_local.ps1 게이트 + GitHub Actions CI(`test.yml`). 군포 용적률 1% garbage 적발·수정.
- ✅ **주소 카드 미지원 지역 fallback 수정** — 군 등 매칭 실패 시 서울 카드 오표시 → "시 단위 카드 미지원(용도지역만 확인)" 안내.
- ✅ **C-1 검색 고도화** — 동의어(20그룹)+초성. `web/src/search.js`.
- ✅ **C-2 인용 관계 시각화** — Reader `CiteGraph`(좌=피인용·우=인용).
- ✅ **C-3 채팅 벡터 RAG** — Voyage 1024d, `embeddings.npy`, 코사인 top_k+키워드 폴백.
- ✅ **C-3 확장 RAG 하이브리드** — RRF+도메인핀+max_chars. `builder/eval_rag.py` 34문항. 결론 일치 38→88%, 법령 인용 59→97%. 잔존: pk_busan 데이터 부재(guard), complex/incentive 복합추론.
- ✅ **주소→용도지역 자동조회(VWorld)** — `/api/zoning`, REGIONS 매칭+zone 자동선택.
- ✅ **A-1 LLM 카드 보강** — 이격 64→77·주차 65→66·심의 46→77. 이격 별표없음 7개시(여주·동두천·원주·논산·영천·문경·양산)·수원 주차는 영구 guard.
