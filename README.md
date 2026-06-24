# arch-law-graph

건축 법령 체계를 **관계 그래프로 구축**하고 **2D 인터랙티브 네트워크**로 시각화하는 단독 웹앱.
자매 앱 [`arch-law-diagnose`](../arch-law-diagnose) 의 법제처 연동 코드를 재활용한다.

> ⚠️ 참고용 시각화 자산. 정확도·법적 효력을 주장하지 않는다. 실무 진단은 `arch-law-diagnose` 담당.

전체 기획·스펙은 **[arch-law-graph-KICKOFF.md](../arch-law-diagnose/arch-law-graph-KICKOFF.md)** 참조.

## 구조

```
builder/   # Python — 법제처 fetch → 그래프 빌드 (Phase 1)
web/       # React + Vite + react-force-graph-2d — 시각화 (Phase 2)
data/      # graph.json 등 산출물
```

## Phase 1 빠른 시작

```
# 자매 앱 venv 재사용 (별도 설치 불필요)
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder\fetch_test.py
```

`.env` 의 `LAW_API_KEY` 를 사용한다 (자매 앱에서 복사됨).

## 진행 상태

- [x] repo 뼈대 + 법제처 클라이언트 이식
- [x] 건축법 1개 법령 fetch 검증 (`builder/fetch_test.py`)
- [x] 엣지 추출 + graph.json 빌드 (`builder/build_graph.py`) — 법령군 11개, node 1590 / edge 4600
- [x] 2D 네트워크 시각화 (`web/`) — Vite + React + react-force-graph-2d

### graph 빌드

```
# 법령군 전체
D:\APPS\arch-law-diagnose\backend\.venv\Scripts\python.exe builder\build_graph.py
# 단일 법령만 (엣지 품질 확인)
... builder\build_graph.py --only 건축법
```

산출물 `data/graph.json` — 엣지 type: `contains`(법→조문) / `references`(같은 법 내 조문 인용) / `cross_law`(타 법령 「」 인용) / `byeolpyo`(별표) / `delegates`(시행령·시행규칙 위임). 각 추출 엣지에 `evidence`(원문 발췌) 보존.

## Phase 2 — 2D 시각화 (`web/`)

```bash
cd web
npm install
npm run dev        # http://localhost:5173
```

`data/graph.json` 을 직접 import (vite `fs.allow: ['..']`). graph 재빌드 시 자동 반영(HMR).

- 노드 색 = `domain_tags`(8 카테고리), 크기 = 피인용 수(contains 제외 in-degree)
- 엣지 스타일 = type별 (위임 주황 실선+화살표 / 참조 점선 / 타법령·별표 색 구분)
- 인터랙션: 노드 클릭 → 조문 상세(본문·시행일·원문 링크), 호버 → 이웃만 강조, 검색(조문명·번호·법령명), 도메인·법령 필터 토글
