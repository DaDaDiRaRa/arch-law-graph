// 모든 뷰가 공유하는 graph.json 파생 데이터 + 색상 헬퍼
// graph.json(53MB)을 JS 번들에 인라인하지 않고 별도 정적 에셋(?url)으로 분리해
// 런타임 fetch. top-level await 로 이 모듈을 import 하는 쪽은 자동으로 로드 완료까지 대기
// → 소비자 코드 무수정. 번들 JS 대폭 감소 + graph 독립 캐싱 + JSON.parse(빠름).
import graphUrl from "../../data/graph.json?url";
const rawGraph = await fetch(graphUrl).then((r) => r.json());

export const meta = rawGraph.meta || {};
export const nodes = rawGraph.nodes;
export const links = rawGraph.links;

const idOf = (x) => (typeof x === "object" ? x.id : x);

// ─── 법령(군 내부) 목록 ──────────────────────────────────────────────────
export const internalLaws = nodes
  .filter((n) => n.type === "law" && !n.external)
  .map((n) => n.id);
const internalSet = new Set(internalLaws);

// 행정규칙(고시)·자치법규(조례) 노드 집합 — 색상·라벨에서 법령과 구분
const admrulSet = new Set(
  nodes.filter((n) => n.type === "law" && n.category === "고시").map((n) => n.id)
);
const ordinSet = new Set(
  nodes.filter((n) => n.type === "law" && n.category === "조례").map((n) => n.id)
);
const precSet = new Set(
  nodes.filter((n) => n.type === "law" && n.category === "판례").map((n) => n.id)
);
const expcSet = new Set(
  nodes.filter((n) => n.type === "law" && n.category === "해석례").map((n) => n.id)
);
export const isAdmrul = (name) => admrulSet.has(name);
export const isOrdin = (name) => ordinSet.has(name);
const ADMRUL_HUE = "#7950f2"; // 고시 = 보라
const ORDIN_HUE = "#e64980"; // 조례 = 분홍
const PREC_HUE = "#343a40"; // 판례 = 진회색
const EXPC_HUE = "#0c8599"; // 해석례 = 청록

// ─── 법령군(family) → 색상 ───────────────────────────────────────────────
// 절제된 팔레트: 군별 1 hue. 시행령/규칙은 같은 hue 명도 차.
const FAMILY = [
  // 건축법 패밀리 — 본법·시행령·규칙 + 위임 부령(피난방화·설비·구조·대장)
  {
    test: (n) =>
      n.startsWith("건축법") ||
      /^건축물의 (피난|설비|구조)/.test(n) ||
      n.startsWith("건축물대장"),
    hue: "#4dabf7",
    name: "건축법",
  },
  { test: (n) => n.startsWith("국토의 계획"), hue: "#51cf66", name: "국토계획법" },
  { test: (n) => n.startsWith("주차장법"), hue: "#ffa94d", name: "주차장법" },
  { test: (n) => n.startsWith("건축물의 분양"), hue: "#cc5de8", name: "분양법" },
  { test: (n) => n.startsWith("녹색건축물"), hue: "#20c997", name: "녹색건축물법" },
];

function shade(hex, factor) {
  const r = Math.round(parseInt(hex.slice(1, 3), 16) * factor);
  const g = Math.round(parseInt(hex.slice(3, 5), 16) * factor);
  const b = Math.round(parseInt(hex.slice(5, 7), 16) * factor);
  const c = (v) => Math.min(255, v).toString(16).padStart(2, "0");
  return `#${c(r)}${c(g)}${c(b)}`;
}

export function lawColor(name) {
  if (admrulSet.has(name)) return ADMRUL_HUE; // 고시
  if (ordinSet.has(name)) return ORDIN_HUE; // 조례
  if (precSet.has(name)) return PREC_HUE; // 판례
  if (expcSet.has(name)) return EXPC_HUE; // 해석례
  const fam = FAMILY.find((f) => f.test(name));
  if (!fam) return "#868e96"; // 외부/기타
  if (name.endsWith("시행규칙")) return shade(fam.hue, 0.6);
  if (name.endsWith("시행령")) return shade(fam.hue, 0.8);
  if (name.endsWith("규칙")) return shade(fam.hue, 0.6); // 위임 부령(…에 관한 규칙)
  return fam.hue;
}

export function familyOf(name) {
  if (admrulSet.has(name)) return "고시";
  if (ordinSet.has(name)) return "조례";
  if (precSet.has(name)) return "판례";
  if (expcSet.has(name)) return "해석례";
  return FAMILY.find((f) => f.test(name))?.name || "기타";
}

// ─── 피인용 수 (contains 제외 in-degree) ─────────────────────────────────
export const citeIn = (() => {
  const m = new Map();
  for (const l of links) {
    if (l.type === "contains") continue;
    const t = idOf(l.target);
    m.set(t, (m.get(t) || 0) + 1);
  }
  return m;
})();

// ─── 법령별 조문 목록 (트리 뷰용) ────────────────────────────────────────
export const articlesByLaw = (() => {
  const m = new Map();
  for (const law of internalLaws) m.set(law, []);
  for (const n of nodes) {
    if (n.type === "article" && m.has(n.law_nm)) m.get(n.law_nm).push(n);
  }
  return m;
})();

// 조문 id → 노드 (탐색 뷰 인용 미리보기용)
export const nodeById = new Map(nodes.map((n) => [n.id, n]));

// ─── 법령 ↔ 법령 인용 매트릭스 (Chord 뷰용) ──────────────────────────────
// cross_law 엣지(article→law)를 출발 법령 기준으로 집계. 군 내부 법령만.
export function citationMatrix() {
  const idx = new Map(internalLaws.map((l, i) => [l, i]));
  const n = internalLaws.length;
  const M = Array.from({ length: n }, () => new Array(n).fill(0));
  for (const l of links) {
    if (l.type !== "cross_law") continue;
    const srcNode = nodeById.get(idOf(l.source));
    const srcLaw = srcNode?.law_nm;
    const tgtLaw = idOf(l.target);
    if (idx.has(srcLaw) && idx.has(tgtLaw) && srcLaw !== tgtLaw) {
      M[idx.get(srcLaw)][idx.get(tgtLaw)] += 1;
    }
  }
  return { matrix: M, laws: internalLaws };
}

// ─── 위임 흐름 (Sankey 뷰용) ─────────────────────────────────────────────
// delegates 엣지(법령→하위법령)를 그대로 사용.
export function delegateFlows() {
  const used = new Set();
  const flows = [];
  for (const l of links) {
    if (l.type !== "delegates") continue;
    const s = idOf(l.source);
    const t = idOf(l.target);
    if (internalSet.has(s) && internalSet.has(t)) {
      flows.push({ source: s, target: t });
      used.add(s);
      used.add(t);
    }
  }
  return { flows, laws: [...used] };
}

// 법령의 위계 단계 (0=법률, 1=시행령, 2=시행규칙)
export function tier(name) {
  if (name.endsWith("시행규칙")) return 2;
  if (name.endsWith("시행령")) return 1;
  if (name.endsWith("규칙")) return 2; // 위임 부령은 규칙(부령) 위계
  return 0;
}

// ─── 1-hop 관계 (탐색 뷰 ②: 미니맵·목록용) ───────────────────────────────
// contains(법→조문 구조) 제외. 방향 보존.
export const outRel = new Map(); // id → [{id, type}]  이 조문이 인용한
export const inRel = new Map(); //  id → [{id, type}]  이 조문을 인용한
for (const l of links) {
  if (l.type === "contains") continue;
  const s = idOf(l.source);
  const t = idOf(l.target);
  if (!outRel.has(s)) outRel.set(s, []);
  outRel.get(s).push({ id: t, type: l.type });
  if (!inRel.has(t)) inRel.set(t, []);
  inRel.get(t).push({ id: s, type: l.type });
}

// 노드 id → 소속 법령명 (article=law_nm, law=자기 자신)
export function lawOf(id) {
  const n = nodeById.get(id);
  if (!n) return id;
  return n.type === "law" ? n.id : n.law_nm;
}

// ─── 도메인(주제) — 차별화 핵심: 주제로 법 횡단 ──────────────────────────
export const DOMAINS = [
  "건폐율", "용적률", "높이·일조", "주차",
  "조경", "설비·소방", "행위제한", "도시계획시설",
];

// 도메인별 조문 수
export const domainCount = (() => {
  const m = new Map(DOMAINS.map((d) => [d, 0]));
  for (const n of nodes) {
    if (n.type !== "article") continue;
    for (const t of n.domain_tags || []) if (m.has(t)) m.set(t, m.get(t) + 1);
  }
  return m;
})();

export const maxCite = Math.max(1, ...[...citeIn.values()]);
