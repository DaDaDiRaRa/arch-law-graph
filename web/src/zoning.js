// 용도지역별 규제 기준 — 멀티리전(13개 지자체) 큐레이션 조회 테이블.
// 모든 수치는 graph.json 의 실재 조문/별표에서 대조. 각 수치는 열어볼 수 있는 근거 조문 id를 가리킴.
//   nat = 국가 상한(시행령 제84·85조, 전국 공통), sel = 도시별 조례 적용값.
//   ※ 도시마다 존재하는 용도지역이 다름(서울·수원은 16, 그 외 광역시·시는 17~21).
//   ※ 울산·창원 건폐율·용적률은 도시계획 조례 별표(HWP)에서 추출.

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
  {
    code: "27", name: "대구광역시",
    refs: refs("대구광역시 도시계획 조례/제75조", "대구광역시 도시계획 조례/제80조", "대구광역시 건축 조례/제40조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 40, far: 120 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 220 }, "3il": { bcr: 50, far: 250 },
      "junju": { bcr: 60, far: 400, farNote: "공동주택 250%·주거복합 300%" },
      "jungsang": { bcr: 80, far: 1300 }, "ilsang": { bcr: 70, far: 1000 },
      "geunsang": { bcr: 70, far: 800 }, "yutong": { bcr: 70, far: 900 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 60 }, "saengnok": { bcr: 20, far: 100 }, "janok": { bcr: 20, far: 100 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 }, "jayeon": { bcr: 20, far: 80 },
    },
  },
  {
    code: "29", name: "광주광역시",
    refs: refs("광주광역시 도시계획 조례/제67조", "광주광역시 도시계획 조례/제72조", "광주광역시 건축 조례/제35조"),
    zones: {
      "1jeon": { bcr: 40, far: 80 }, "2jeon": { bcr: 40, far: 120 },
      "1il": { bcr: 60, far: 150 }, "2il": { bcr: 60, far: 220, farNote: "택지·도시개발·산단 200%" }, "3il": { bcr: 50, far: 250 },
      "junju": { bcr: 60, far: 400 },
      "jungsang": { bcr: 70, far: 1300 }, "ilsang": { bcr: 60, far: 1000 },
      "geunsang": { bcr: 60, far: 700 }, "yutong": { bcr: 60, far: 800 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 60 }, "saengnok": { bcr: 20, far: 60 }, "janok": { bcr: 20, far: 60 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 90 },
      "nongrim": { bcr: 20, far: 60 }, "jayeon": { bcr: 20, far: 60 },
    },
  },
  {
    code: "30", name: "대전광역시",
    refs: refs("대전광역시 도시계획 조례/제45조", "대전광역시 도시계획 조례/제50조", "대전광역시 건축 조례/제43조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 40, far: 120 },
      "1il": { bcr: 60, far: 150 }, "2il": { bcr: 60, far: 200 }, "3il": { bcr: 50, far: 250 },
      "junju": { bcr: 60, far: 400 },
      "jungsang": { bcr: 80, far: 1300 }, "ilsang": { bcr: 70, far: 1100 },
      "geunsang": { bcr: 60, far: 700 }, "yutong": { bcr: 70, far: 900 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 60 }, "saengnok": { bcr: 20, far: 70 }, "janok": { bcr: 20, far: 80 },
      "bojgwan": { bcr: 20, far: 60 }, "saenggwan": { bcr: 20, far: 70 }, "gyehoek": { bcr: 40, far: 80 },
      "nongrim": { bcr: 20, far: 70 }, "jayeon": { bcr: 20, far: 60 },
    },
  },
  {
    code: "31", name: "울산광역시",
    refs: refs("울산광역시 도시계획 조례/별표24", "울산광역시 도시계획 조례/별표24", "울산광역시 건축 조례/제55조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 50, far: 150 },
      "1il": { bcr: 60, far: 150 }, "2il": { bcr: 60, far: 200 }, "3il": { bcr: 50, far: 300 },
      "junju": { bcr: 70, far: 500 },
      "jungsang": { bcr: 80, far: 1300 }, "ilsang": { bcr: 70, far: 1200 },
      "geunsang": { bcr: 60, far: 700 }, "yutong": { bcr: 70, far: 900 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 80 }, "saengnok": { bcr: 20, far: 100 }, "janok": { bcr: 20, far: 100 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 }, "jayeon": { bcr: 20, far: 80 },
    },
  },
  {
    code: "36", name: "세종특별자치시",
    refs: refs("세종특별자치시 도시계획 조례/제50조", "세종특별자치시 도시계획 조례/제54조", "세종특별자치시 건축 조례/제40조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 50, far: 150 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 250 }, "3il": { bcr: 50, far: 300 },
      "junju": { bcr: 70, far: 400 },
      "jungsang": { bcr: 80, far: 1300 }, "ilsang": { bcr: 80, far: 1100 },
      "geunsang": { bcr: 70, far: 700 }, "yutong": { bcr: 80, far: 900 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 80 }, "saengnok": { bcr: 20, far: 100 }, "janok": { bcr: 20, far: 100 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 }, "jayeon": { bcr: 20, far: 80 },
    },
  },
  {
    code: "41110", name: "수원시",
    refs: refs("수원시 도시계획 조례/제66조", "수원시 도시계획 조례/제70조", "수원시 건축 조례/제41조"),
    zones: {
      "1jeon": { bcr: 40, far: 100 }, "2jeon": { bcr: 30, far: 150 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 250, farNote: "공동주택 230%" }, "3il": { bcr: 40, far: 300, farNote: "공동주택 230%" },
      "junju": { bcr: 70, far: 400 },
      "jungsang": { bcr: 90, far: 1000 }, "ilsang": { bcr: 80, far: 800 },
      "geunsang": { bcr: 70, far: 600 }, "yutong": { bcr: 60, far: 400 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 60, far: 350 }, "jungong": { bcr: 60, far: 400 },
      "bojnok": { bcr: 20, far: 50 }, "saengnok": { bcr: 20, far: 100 }, "janok": { bcr: 20, far: 100 },
    },
  },
  {
    code: "41280", name: "고양시",
    refs: refs("고양시 도시계획 조례/제56조", "고양시 도시계획 조례/제61조", "고양시 건축 조례/제41조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 50, far: 150 },
      "1il": { bcr: 60, far: 180 }, "2il": { bcr: 60, far: 230 }, "3il": { bcr: 50, far: 250 },
      "junju": { bcr: 60, far: 380 },
      "jungsang": { bcr: 80, far: 1200 }, "ilsang": { bcr: 70, far: 900 },
      "geunsang": { bcr: 60, far: 700 }, "yutong": { bcr: 70, far: 400 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 50 }, "saengnok": { bcr: 20, far: 90 }, "janok": { bcr: 20, far: 100 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 }, "jayeon": { bcr: 20, far: 50 },
    },
  },
  {
    code: "41460", name: "용인시",
    refs: refs("용인시 도시계획 조례/제50조", "용인시 도시계획 조례/제55조", "용인시 건축 조례/제36조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 50, far: 150 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 240 }, "3il": { bcr: 50, far: 290 },
      "junju": { bcr: 70, far: 450 },
      "jungsang": { bcr: 90, far: 1100 }, "ilsang": { bcr: 80, far: 900 },
      "geunsang": { bcr: 70, far: 700 }, "yutong": { bcr: 80, far: 800 },
      "jeongong": { bcr: 70, far: 250 }, "ilgong": { bcr: 70, far: 300 }, "jungong": { bcr: 70, far: 350 },
      "bojnok": { bcr: 20, far: 70 }, "saengnok": { bcr: 20, far: 100 }, "janok": { bcr: 20, far: 100 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 70 }, "jayeon": { bcr: 20, far: 70 },
    },
  },
  {
    code: "48120", name: "창원시",
    refs: refs("창원시 도시계획 조례/별표27", "창원시 도시계획 조례/별표28", "창원시 건축 조례/제33조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 50, far: 150 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 220 }, "3il": { bcr: 50, far: 250 },
      "junju": { bcr: 70, far: 400, farNote: "창원신도시 건폐 60%" },
      "jungsang": { bcr: 80, far: 1000 }, "ilsang": { bcr: 80, far: 1000 },
      "geunsang": { bcr: 70, far: 700 }, "yutong": { bcr: 80, far: 700 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400, farNote: "읍·면지역 200%" },
      "bojnok": { bcr: 20, far: 80 }, "saengnok": { bcr: 20, far: 100 }, "janok": { bcr: 20, far: 100 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 }, "jayeon": { bcr: 20, far: 80 },
    },
  },
  {
    code: "50", name: "제주특별자치도",
    refs: refs("제주특별자치도 도시계획 조례/제60조", "제주특별자치도 도시계획 조례/제61조", "제주특별자치도 건축 조례/제30조"),
    zones: {
      "1jeon": { bcr: 40, far: 80 }, "2jeon": { bcr: 40, far: 120 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 250 }, "3il": { bcr: 50, far: 300 },
      "junju": { bcr: 60, far: 500 },
      "jungsang": { bcr: 80, far: 1300 }, "ilsang": { bcr: 80, far: 1000 },
      "geunsang": { bcr: 60, far: 700 }, "yutong": { bcr: 70, far: 700 },
      "jeongong": { bcr: 60, far: 200, farNote: "주용도 공장·창고 건폐 70%" }, "ilgong": { bcr: 60, far: 300 }, "jungong": { bcr: 60, far: 300 },
      "bojnok": { bcr: 20, far: 60 }, "saengnok": { bcr: 20, far: 60 }, "janok": { bcr: 20, far: 80 },
      "bojgwan": { bcr: 20, far: 60 }, "saenggwan": { bcr: 20, far: 60 }, "gyehoek": { bcr: 40, far: 80 },
      "nongrim": { bcr: 20, far: 50 }, "jayeon": { bcr: 20, far: 50 },
    },
  },
  {
    code: "41130", name: "성남시",
    refs: refs("성남시 도시계획 조례/제66조", "성남시 도시계획 조례/제67조", "성남시 건축 조례/제27조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 50, far: 120 },
      "1il": { bcr: 60, far: 160 }, "2il": { bcr: 60, far: 210, farNote: "정비사업 아파트 250%" }, "3il": { bcr: 50, far: 280, farNote: "정비사업 아파트 300%" },
      "junju": { bcr: 70, far: 400 },
      "jungsang": { bcr: 80, far: 1000 }, "ilsang": { bcr: 80, far: 800 },
      "geunsang": { bcr: 70, far: 600 }, "yutong": { bcr: 80, far: 600 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 400 },
      "bojnok": { bcr: 20, far: 70 }, "saengnok": { bcr: 20, far: 50 }, "janok": { bcr: 20, far: 100 },
    },
  },
  {
    code: "43110", name: "청주시",
    refs: refs("청주시 도시계획 조례/제61조", "청주시 도시계획 조례/제67조", "청주시 건축 조례/제35조"),
    zones: {
      "1jeon": { bcr: 40, far: 80, farNote: "도시및주거환경정비법 100%" }, "2jeon": { bcr: 50, far: 120, farNote: "도시및주거환경정비법 150%" },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 250, farNote: "아파트 230%" }, "3il": { bcr: 50, far: 300 },
      "junju": { bcr: 70, far: 500 },
      "jungsang": { bcr: 80, far: 1000 }, "ilsang": { bcr: 80, far: 1000 },
      "geunsang": { bcr: 70, far: 900 }, "yutong": { bcr: 70, far: 600 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 60, far: 350 },
      "bojnok": { bcr: 20, far: 80 }, "saengnok": { bcr: 20, far: 80 }, "janok": { bcr: 20, far: 100 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 }, "jayeon": { bcr: 20, far: 80 },
    },
  },
  {
    code: "45110", name: "전주시",
    refs: refs("전주시 도시계획 조례/제45조", "전주시 도시계획 조례/제47조", "전주시 건축 조례/제42조"),
    zones: {
      "1jeon": { bcr: 40, far: 100 }, "2jeon": { bcr: 40, far: 100 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 250 }, "3il": { bcr: 50, far: 300 },
      "junju": { bcr: 60, far: 500 },
      "jungsang": { bcr: 80, far: 1100, farNote: "주거복합·오피스텔 700%" }, "ilsang": { bcr: 70, far: 900, farNote: "주거복합·오피스텔 600%" },
      "geunsang": { bcr: 60, far: 700, farNote: "주거복합·오피스텔 500%" }, "yutong": { bcr: 60, far: 700, farNote: "오피스텔 400%" },
      "jeongong": { bcr: 60, far: 300 }, "ilgong": { bcr: 60, far: 350 }, "jungong": { bcr: 60, far: 400, farNote: "공동주택 200%" },
      "bojnok": { bcr: 20, far: 50 }, "saengnok": { bcr: 20, far: 100 }, "janok": { bcr: 20, far: 100 },
      "bojgwan": { bcr: 20, far: 50 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 },
    },
  },
  {
    code: "44130", name: "천안시",
    refs: refs("천안시 도시계획 조례/제56조", "천안시 도시계획 조례/제61조", "천안시 건축 조례/제38조"),
    zones: {
      "1jeon": { bcr: 50, far: 100 }, "2jeon": { bcr: 50, far: 150 },
      "1il": { bcr: 60, far: 200 }, "2il": { bcr: 60, far: 250 }, "3il": { bcr: 50, far: 300 },
      "junju": { bcr: 70, far: 500 },
      "jungsang": { bcr: 90, far: 1200 }, "ilsang": { bcr: 80, far: 1100 },
      "geunsang": { bcr: 70, far: 700 }, "yutong": { bcr: 80, far: 700 },
      "jeongong": { bcr: 70, far: 300 }, "ilgong": { bcr: 70, far: 350 }, "jungong": { bcr: 70, far: 350 },
      "bojnok": { bcr: 20, far: 60 }, "saengnok": { bcr: 20, far: 80 }, "janok": { bcr: 20, far: 80 },
      "bojgwan": { bcr: 20, far: 80 }, "saenggwan": { bcr: 20, far: 80 }, "gyehoek": { bcr: 40, far: 100 },
      "nongrim": { bcr: 20, far: 80 }, "jayeon": { bcr: 20, far: 60 },
    },
  },
];

// 도시의 zone 목록을 ZONE_DEFS 순서로 반환 (selector·카드용).
export function zonesOf(region) {
  return ZONE_DEFS.filter((d) => region.zones[d.key]).map((d) => ({
    ...d, ...region.zones[d.key],   // bcrNat/farNat(def) + bcr/far/farNote(region)
  }));
}
