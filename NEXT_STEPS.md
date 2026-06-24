# 다음 작업 (핸드오프)

> 새 세션 시작 시: **이 파일 + `README.md` + `D:\APPS\arch-law-diagnose\arch-law-graph-KICKOFF.md`(전체 기획)** 를 먼저 읽고 이어서 진행.

---

## 0. 환경 (그대로 재사용)

- **Python**: 별도 venv 만들지 말고 자매 앱 venv 재사용
  `D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe`
  (httpx·dotenv·networkx 등 이미 설치돼 있음. 없으면 `pip install -r builder\requirements.txt`)
- **실행 위치**: 항상 프로젝트 루트(`D:\APPS\arch-law-graph`)에서 — `.env`(LAW_API_KEY·ANTHROPIC_API_KEY)가 루트에 있음
- **Windows 콘솔 한글 깨짐**: 스크립트 맨 위에 `sys.stdout.reconfigure(encoding="utf-8")` (fetch_test.py 참고)

## 0-1. 이미 끝난 것 ✅

- repo 뼈대(`builder/`·`web/`·`data/`), `.gitignore`, `README.md`
- `builder/law_go_kr_client.py` 이식 + **법률/조례 두 XML 스키마 자동 분기 파서**로 수정 완료
  - 법률(target=law): `<조문단위>` (조문여부 `'조문'`=실제, `'전문'`=장/절구분자)
  - 조례(target=ordin): `<조>` (조문여부 Y/N)
- `builder/fetch_test.py` — 건축법 fetch 검증 통과(**166개 조문** 정상 파싱)

---

## 1. 다음 작업: `builder/build_graph.py` (Phase 1 핵심)

목표: 법령군을 fetch → 노드/엣지 추출 → `data/graph.json` 생성.

### 1-1. 대상 법령군 정의

```python
LAW_GROUP = [
    "건축법", "건축법 시행령", "건축법 시행규칙",
    "국토의 계획 및 이용에 관한 법률",
    "국토의 계획 및 이용에 관한 법률 시행령",
    "국토의 계획 및 이용에 관한 법률 시행규칙",
    "주차장법", "주차장법 시행령", "주차장법 시행규칙",
    "건축물의 분양에 관한 법률",
    "녹색건축물 조성 지원법",
    # 필요 시 확장
]
```
- 각 법령명을 `search_law(name, "LAW")` 로 조회 → **법령명이 정확히 일치하는 항목** 선택(부분일치 주의: "건축법"이 "건축법 시행령"보다 먼저 와야 함 → `==` 비교)
- MST는 시행일마다 바뀌니 **하드코딩 금지**, 매번 검색

### 1-2. 노드 생성

- `law` 노드: 법령당 1개. `{id: 법령명, type:"law", law_nm, ...}`
- `article` 노드: 조문당 1개. `id = f"{법령명}/제{article_no}조"` (가지번호는 `의N`)
- 속성: `title`, `content`, `ef_yd`, `domain_tags`, `source_url`
- **law → 소속 article** 엣지(`type:"contains"`)도 넣어 군집이 모이게

### 1-3. 엣지 추출 (regex, content 본문에서)

| 엣지 type | 패턴(예시) | 타깃 |
|---|---|---|
| `references` | `제(\d+)조(의(\d+))?` | 같은 법령 내 해당 조문 노드 |
| `cross_law` | `「([^」]+)」` | 인용된 법령명 노드(있으면 연결, 없으면 외부 노드 stub) |
| `byeolpyo` | `별표\s*(\d+)` | `별표N` 노드 |
| `delegates` | `대통령령으로 정하` / `국토교통부령으로 정하` / `행정안전부령으로 정하` | 법→시행령 / 법·령→시행규칙 (법령 단위 엣지) |

- 각 엣지에 **`method:"regex"`** + **`evidence`(매칭된 원문 30~60자)** 필수 보존
- 모호한 위임("따로 정한다" 등)은 일단 스킵 → 나중에 LLM 보조(자매 앱 `ordinance_extractor._llm_extract` 패턴 차용, `method:"llm"` 표시)
- ⚠️ 인용 해소(resolve) 시 같은 법령 내 우선. "제2조제1항제4호" 같이 항·호까지 붙은 건 조까지만 연결(항·호는 본문 인라인)

### 1-4. domain_tags 분류 (8 카테고리)

키워드 기반 룰. content/title에 매칭:
`건폐율 / 용적률 / 높이·일조 / 주차 / 조경 / 설비·소방 / 행위제한 / 도시계획시설`
(자매 앱 진단 8카테고리와 동일. 매칭 0개면 `["기타"]`)

### 1-5. export

```python
import networkx as nx, json
G = nx.DiGraph()  # 노드·엣지 추가
data = nx.node_link_data(G)
data["meta"] = {"built_at": "...", "law_count": N, "node_count": ..., "edge_count": ...}
# data/graph.json 으로 ensure_ascii=False 저장
```
- `built_at` 등 시각은 인자로 넣거나 실행 시 stamp (스크립트 내 datetime.now() 사용 가능 — 일반 실행이므로 OK)

### 1-6. 완료 기준

- `python builder\build_graph.py` 실행 → `data/graph.json` 생성
- 콘솔에 law/node/edge 수 출력
- graph.json 열어 **엣지마다 evidence 원문이 들어있는지** 눈으로 확인
- 먼저 **건축법 1개만** 돌려 엣지 품질 확인 → 이상 없으면 법령군 전체로 확장

---

## 2. 그 다음: `web/` 2D 네트워크 시각화 (Phase 2)

1. `web/` 에 Vite + React 스캐폴드, `react-force-graph-2d` 설치
2. `data/graph.json` 을 import 또는 fetch → `<ForceGraph2D graphData={...} />` 최소 렌더(점+선)
3. 스타일: 노드 색=domain_tags, 크기=in-degree(피인용), 엣지=type별(위임 실선/참조 점선/LLM 흐리게)
4. 인터랙션: 노드 클릭→조문 상세 패널(title·content·ef_yd·source_url), 호버→이웃만 강조, 검색(조문명/번호), 도메인·법령 필터 토글
5. 하단 면책 문구("참고용 시각화, 법적 효력 없음")
6. (여유) 네트워크 ↔ 계층 트리 뷰 토글

완료 기준: 브라우저에서 그래프가 뜨고, 클릭 시 조문 본문이 보이고, 검색·필터·이웃강조 동작.

---

## 3. 이후

- 법령군 전체 빌드 안정화 → 조례(target=ordin) 확장(파서는 이미 지원)
- LLM 보조 엣지 추출(묵시적 위임)
- 배포: graph.json 정적 서빙(Docker→Cloud Run 또는 정적 호스팅)
- (선택) 노드 클릭 → 자매 앱 실제 법규 조회 API 연결

---

## 막혔을 때 디버깅

- fetch 0건: `.env` LAW_API_KEY 확인, 루트에서 실행했는지 확인
- 조문 1건(전문)만 나옴: 파서 분기 문제 — 법률은 `<조문단위>`, 조례는 `<조>` (이미 수정됨)
- XML 구조 의심되면 일회성 프로브로 `root.iter()` 태그 빈도 덤프해 확인
