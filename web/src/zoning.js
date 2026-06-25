// 용도지역별 규제 기준 — 멀티리전(서울·부산·인천) 큐레이션 조회 테이블.
// 모든 수치는 graph.json 의 실재 조문에서 대조. 각 수치는 열어볼 수 있는 근거 조문 id를 가리킴.
//   nat = 국가 상한(시행령 제84·85조, 전국 공통), sel = 도시별 조례 적용값.
//   ※ 도시마다 존재하는 용도지역이 다름(서울 16·부산 17·인천 21).

const L_GUKTO = "국토의 계획 및 이용에 관한 법률";
const L_GUKTO_D = "국토의 계획 및 이용에 관한 법률 시행령";
const L_ARCH = "건축법";
const L_ARCH_D = "건축법 시행령";

// 정북 일조 규칙 — 시행령 제86조 위임, 서울·부산·인천 모두 동일(10m↓ 1.5m / 초과 1/2).
export const SUNLIGHT_RULE =
  "정북방향 인접대지경계선에서 — 높이 10m 이하: 1.5m 이상, 10m 초과: 해당 높이의 1/2 이상 이격";

// ─── 용도지역 마스터(전국 공통 정의 + 국가 상한) ─────────────────────────
// bcrNat=시행령 제84조, farNat=시행령 제85조 상한. sunlight=정북 일조제한 적용.
export const ZONE_DEFS = [
  { key: "1jeon", label: "제1종전용주거지역", group: "주거", bcrNat: 50, farNat: 100, sunlight: true },
  { key: "2jeon", label: "제2종전용주거지역", group: "주거", bcrNat: 50, farNat: 150, sunlight: true },
  { key: "1il",   label: "제1종일반주거지역", group: "주거", bcrNat: 60, farNat: 200, sunlight: true },
  { key: "2il",   label: "제2종일반주거지역", group: "주거", bcrNat: 60, farNat: 250, sunlight: true },
  { key: "3il",   label: "제3종일반주거지역", group: "주거", bcrNat: 50, farNat: 300, sunlight: true },
  { key: "junju", label: "준주거지역",        group: "주거", bcrNat: 70, farNat: 500, sunlight: false },
  { key: "jungsang", label: "중심상업지역", group: "상업", bcrNat: 90, farNat: 1500, sunlight: false },
  { key: "ilsang",   label: "일반상업지역", group: "상업", bcrNat: 80, farNat: 1300, sunlight: false },
  { key: "geunsang", label: "근린상업지역", group: "상업", bcrNat: 70, farNat: 900,  sunlight: false },
  { key: "yutong",   label: "유통상업지역", group: "상업", bcrNat: 80, farNat: 1100, sunlight: false },
  { key: "jeongong", label: "전용공업지역", group: "공업", bcrNat: 70, farNat: 300, sunlight: false },
  { key: "ilgong",   label: "일반공업지역", group: "공업", bcrNat: 70, farNat: 350, sunlight: false },
  { key: "jungong",  label: "준공업지역",   group: "공업", bcrNat: 70, farNat: 400, sunlight: false },
  { key: "bojnok",   label: "보전녹지지역", group: "녹지", bcrNat: 20, farNat: 80,  sunlight: false },
  { key: "saengnok", label: "생산녹지지역", group: "녹지", bcrNat: 20, farNat: 100, sunlight: false },
  { key: "janok",    label: "자연녹지지역", group: "녹지", bcrNat: 20, farNat: 100, sunlight: false },
  { key: "bojgwan",  label: "보전관리지역", group: "관리", bcrNat: 20, farNat: 80,  sunlight: false },
  { key: "saenggwan",label: "생산관리지역", group: "관리", bcrNat: 20, farNat: 80,  sunlight: false },
  { key: "gyehoek",  label: "계획관리지역", group: "관리", bcrNat: 40, farNat: 100, sunlight: false },
  { key: "nongrim",  label: "농림지역",     group: "기타", bcrNat: 20, farNat: 80,  sunlight: false },
  { key: "jayeon",   label: "자연환경보전지역", group: "기타", bcrNat: 20, farNat: 80, sunlight: false },
];
export const ZONE_GROUPS = ["주거", "상업", "공업", "녹지", "관리", "기타"];

const refs = (dosiBcr, dosiFar, archSun) => ({
  bcr: [`${L_GUKTO}/제77조`, `${L_GUKTO_D}/제84조`, dosiBcr],
  far: [`${L_GUKTO}/제78조`, `${L_GUKTO_D}/제85조`, dosiFar],
  sun: [`${L_ARCH}/제61조`, `${L_ARCH_D}/제86조`, archSun],
});

// ─── 도시별 적용값 (조례) ────────────────────────────────────────────────
// zones[key] = { bcr, far, farNote? }. 해당 도시에 존재하는 용도지역만 등재.
export const REGIONS = [
  {
    code: "11", name: "서울특별시",
    refs: refs("서울특별시 도시계획 조례/제44조", "서울특별시 도시계획 조례/제48조", "서울특별시 건축 조례/제35조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 40, far: 120 },
      "1il": { bcr: 60, far: 150 }, "2il": { bcr: 60, far: 200 }, "3il": { bcr: 50, far: 250 },
      "junju": { bcr: 60, far: 400 },
      "jungsang": { bcr: 60, far: 1000, farNote: "서울도심 800%" },
      "ilsang": { bcr: 60, far: 800, farNote: "서울도심 600%" },
      "geunsang": { bcr: 60, far: 600, farNote: "서울도심 500%" },
      "yutong": { bcr: 60, far: 600, farNote: "서울도심 500%" },
      "jeongong": { bcr: 60, far: 200 }, "ilgong": { bcr: 60, far: 200 }, "jungong": { bcr: 60, far: 400 },
      "bojnok": { bcr: 20, far: 50 }, "saengnok": { bcr: 20, far: 50 }, "janok": { bcr: 20, far: 50 },
    },
  },
  {
    code: "26", name: "부산광역시",
    refs: refs("부산광역시 도시계획 조례/제49조", "부산광역시 도시계획 조례/제50조", "부산광역시 건축 조례/제43조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 40, far: 120 },
      "1il": { bcr: 60, far: 180 }, "2il": { bcr: 60, far: 220, farNote: "대지 1,000㎡ 초과 시 200%" }, "3il": { bcr: 50, far: 300 },
      "junju": { bcr: 60, far: 400 },
      "jungsang": { bcr: 80, far: 1300 }, "ilsang": { bcr: 60, far: 1000 },
      "geunsang": { bcr: 60, far: 700 }, "yutong": { bcr: 60, far: 800 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 60 }, "saengnok": { bcr: 20, far: 80 }, "janok": { bcr: 20, far: 80 },
      "jayeon": { bcr: 20, far: 60 },
    },
  },
  {
    code: "28", name: "인천광역시",
    refs: refs("인천광역시 도시계획 조례/제64조", "인천광역시 도시계획 조례/제65조", "인천광역시 건축 조례/제32조"),
    zones: {
      "1jeon": { bcr: 50, far: 80 }, "2jeon": { bcr: 50, far: 120 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 250 }, "3il": { bcr: 50, far: 300 },
      "junju": { bcr: 60, far: 500, farNote: "순수 주거용 공동주택 300%" },
      "jungsang": { bcr: 80, far: 1300 }, "ilsang": { bcr: 70, far: 1000 },
      "geunsang": { bcr: 70, far: 700 }, "yutong": { bcr: 70, far: 800 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 50 }, "saengnok": { bcr: 20, far: 80 }, "janok": { bcr: 20, far: 80 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 }, "jayeon": { bcr: 20, far: 80 },
    },
  },
];

// 도시의 zone 목록을 ZONE_DEFS 순서로 반환 (selector·카드용).
export function zonesOf(region) {
  return ZONE_DEFS.filter((d) => region.zones[d.key]).map((d) => ({
    ...d, ...region.zones[d.key],   // bcrNat/farNat(def) + bcr/far/farNote(region)
  }));
}
