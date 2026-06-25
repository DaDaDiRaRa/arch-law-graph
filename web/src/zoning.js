// 용도지역별 규제 기준 — 손으로 큐레이션한 "결정-등급" 조회 테이블.
// 모든 수치는 graph.json 의 실재 조문 본문에서 대조해 입력했고,
// 각 수치는 열어볼 수 있는 근거 조문 id(아래 *_REFS)를 가리킨다.
// → AI 합성이 아니라, 1차 법령에 추적 가능한 답. 이것이 본 앱의 차별점.
//
// 현재 대상: 서울특별시 (도시지역 16개 용도지역).
//   ※ 서울은 전역이 도시지역 → 관리지역·농림지역·자연환경보전지역은 존재하지 않음.
// 다른 지자체 확장 시: REGION 추가 + 해당 조례 조문 id로 *_REFS·sel 값 교체.

export const REGION = { code: "11", name: "서울특별시" };

// ─── 근거 조문 id (graph.json 노드와 1:1, 존재 확인 완료) ──────────────────
const L_GUKTO = "국토의 계획 및 이용에 관한 법률";
const L_GUKTO_D = "국토의 계획 및 이용에 관한 법률 시행령";
const L_ARCH = "건축법";
const L_ARCH_D = "건축법 시행령";

export const BCR_REFS = [
  `${L_GUKTO}/제77조`,            // 건폐율 위임 본법
  `${L_GUKTO_D}/제84조`,         // 용도지역별 건폐율 범위(국가 상한)
  "서울특별시 도시계획 조례/제44조", // 서울 적용 건폐율
];
export const FAR_REFS = [
  `${L_GUKTO}/제78조`,            // 용적률 위임 본법
  `${L_GUKTO_D}/제85조`,         // 용도지역별 용적률 범위(국가 상한)
  "서울특별시 도시계획 조례/제48조", // 서울 적용 용적률
];
export const SUN_REFS = [
  `${L_ARCH}/제61조`,            // 일조 등 확보 높이제한 위임 본법
  `${L_ARCH_D}/제86조`,          // 정북 이격 범위
  "서울특별시 건축 조례/제35조",   // 서울 적용 이격거리
];
export const HEIGHT_REFS = [
  `${L_ARCH}/제60조`,            // 가로구역별 최고높이
  "서울특별시 건축 조례/제33조",   // 서울 가로구역 높이
];

// 정북 일조 규칙(서울 건축조례 제35조 ①) — 전용주거·일반주거지역 공통
export const SUNLIGHT_RULE =
  "정북방향 인접대지경계선에서 — 높이 10m 이하: 1.5m 이상, 10m 초과: 해당 높이의 1/2 이상 이격";

// ─── 용도지역 16종 (서울) ───────────────────────────────────────────────
// bcrNat/farNat = 국가 상한(시행령 제84·85조), bcrSel/farSel = 서울 적용(조례 제44·48조)
// farNote = 서울 조례상 단서(서울도심 등), sunlight = 정북 일조제한 적용 여부
export const ZONES = [
  // 주거지역
  { key: "1jeon", label: "제1종전용주거지역", group: "주거", bcrNat: 50, bcrSel: 50, farNat: 100, farSel: 100, sunlight: true,
    heightNote: "주거용 2층·8m 이하 / 비주거용 2층·11m 이하 (조례 제33조)" },
  { key: "2jeon", label: "제2종전용주거지역", group: "주거", bcrNat: 50, bcrSel: 40, farNat: 150, farSel: 120, sunlight: true },
  { key: "1il",   label: "제1종일반주거지역", group: "주거", bcrNat: 60, bcrSel: 60, farNat: 200, farSel: 150, sunlight: true },
  { key: "2il",   label: "제2종일반주거지역", group: "주거", bcrNat: 60, bcrSel: 60, farNat: 250, farSel: 200, sunlight: true },
  { key: "3il",   label: "제3종일반주거지역", group: "주거", bcrNat: 50, bcrSel: 50, farNat: 300, farSel: 250, sunlight: true },
  { key: "junju", label: "준주거지역",        group: "주거", bcrNat: 70, bcrSel: 60, farNat: 500, farSel: 400, sunlight: false },
  // 상업지역
  { key: "jungsang", label: "중심상업지역", group: "상업", bcrNat: 90, bcrSel: 60, farNat: 1500, farSel: 1000, farNote: "서울도심 800%", sunlight: false },
  { key: "ilsang",   label: "일반상업지역", group: "상업", bcrNat: 80, bcrSel: 60, farNat: 1300, farSel: 800,  farNote: "서울도심 600%", sunlight: false },
  { key: "geunsang", label: "근린상업지역", group: "상업", bcrNat: 70, bcrSel: 60, farNat: 900,  farSel: 600,  farNote: "서울도심 500%", sunlight: false },
  { key: "yutong",   label: "유통상업지역", group: "상업", bcrNat: 80, bcrSel: 60, farNat: 1100, farSel: 600,  farNote: "서울도심 500%", sunlight: false },
  // 공업지역
  { key: "jeongong", label: "전용공업지역", group: "공업", bcrNat: 70, bcrSel: 60, farNat: 300, farSel: 200, sunlight: false },
  { key: "ilgong",   label: "일반공업지역", group: "공업", bcrNat: 70, bcrSel: 60, farNat: 350, farSel: 200, sunlight: false },
  { key: "jungong",  label: "준공업지역",   group: "공업", bcrNat: 70, bcrSel: 60, farNat: 400, farSel: 400, sunlight: false },
  // 녹지지역
  { key: "bojnok", label: "보전녹지지역", group: "녹지", bcrNat: 20, bcrSel: 20, farNat: 80,  farSel: 50, sunlight: false },
  { key: "saengnok", label: "생산녹지지역", group: "녹지", bcrNat: 20, bcrSel: 20, farNat: 100, farSel: 50, sunlight: false },
  { key: "janok",  label: "자연녹지지역", group: "녹지", bcrNat: 20, bcrSel: 20, farNat: 100, farSel: 50, sunlight: false },
];

export const ZONE_GROUPS = ["주거", "상업", "공업", "녹지"];
