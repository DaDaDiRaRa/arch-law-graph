// 대지의 조경 — 멀티리전(13개 지자체) 연면적 규모별 큐레이션.
// 조경 기준은 법(건축법 제42조①)이 조례에 위임 → 도시별 건축조례가 실제 비율을 정함.
// nat = 시행령 제27조② baseline(공장·물류·소규모 등), sel = 도시 조례 적용값.
//   strict = 서울/부산/인천이 baseline보다 강화, relax = 완화(소규모 대지).

const L_ARCH = "건축법";
const L_ARCH_D = "건축법 시행령";

// 연면적 구간 마스터(전국 공통 라벨 + 국가 baseline)
export const TIER_DEFS = [
  { key: "t2000",  label: "연면적 2,000㎡ 이상", nat: "대지면적의 10% 이상" },
  { key: "t1000",  label: "연면적 1,000㎡ 이상 ~ 2,000㎡ 미만", nat: "1,500~2,000㎡: 5% 이상 (그 미만 조례)" },
  { key: "tu1000", label: "연면적 1,000㎡ 미만", nat: "조례로 정함" },
  { key: "tsmall", label: "소규모 대지 200㎡ 이상 ~ 300㎡ 미만", nat: "대지면적의 10% 이상" },
  { key: "tschool",label: "학교이적지 안의 건축물", nat: "— (조례 특례)" },
];

const lsRefs = (archLand) => [`${L_ARCH}/제42조`, `${L_ARCH_D}/제27조`, archLand];

export const REGIONS_LS = [
  {
    code: "11", name: "서울특별시", refs: lsRefs("서울특별시 건축 조례/제24조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
      tsmall: { sel: "대지면적의 5% 이상", relax: true },
      tschool: { sel: "대지면적의 30% 이상", strict: true },
    },
  },
  {
    code: "26", name: "부산광역시", refs: lsRefs("부산광역시 건축 조례/제25조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "28", name: "인천광역시", refs: lsRefs("인천광역시 건축 조례/제22조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "27", name: "대구광역시", refs: lsRefs("대구광역시 건축 조례/제30조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
      tsmall: { sel: "대지면적의 5% 이상", relax: true },
    },
  },
  {
    code: "29", name: "광주광역시", refs: lsRefs("광주광역시 건축 조례/제27조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 13% 이상", strict: true },
      tu1000: { sel: "대지면적의 7% 이상", strict: true },
      tsmall: { sel: "대지면적의 7% 이상", relax: true },
    },
  },
  {
    code: "30", name: "대전광역시", refs: lsRefs("대전광역시 건축 조례/제32조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
      tsmall: { sel: "대지면적의 5% 이상", relax: true },
    },
  },
  {
    code: "31", name: "울산광역시", refs: lsRefs("울산광역시 건축 조례/제21조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
      tsmall: { sel: "대지면적의 5% 이상", relax: true },
    },
  },
  {
    code: "36", name: "세종특별자치시", refs: lsRefs("세종특별자치시 건축 조례/제29조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "41110", name: "수원시", refs: lsRefs("수원시 건축 조례/제31조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상 (5,000㎡ 이상 18%·중심상업 5%)", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "41280", name: "고양시", refs: lsRefs("고양시 건축 조례/제33조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "41460", name: "용인시", refs: lsRefs("용인시 건축 조례/제28조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상 (상업지역 5%)" },
    },
  },
  {
    code: "48120", name: "창원시", refs: lsRefs("창원시 건축 조례/제26조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "50", name: "제주특별자치도", refs: lsRefs("제주특별자치도 건축 조례/제23조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "41130", name: "성남시", refs: lsRefs("성남시 건축 조례/제19조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "43110", name: "청주시", refs: lsRefs("청주시 건축 조례/제28조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "45110", name: "전주시", refs: lsRefs("전주시 건축 조례/제32조"),
    tiers: {
      t2000: { sel: "5천㎡↑ 18% / 4천~5천㎡ 17% / 3천~4천㎡ 16% / 2천~3천㎡ 15%", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
  {
    code: "44130", name: "천안시", refs: lsRefs("천안시 건축 조례/제28조"),
    tiers: {
      t2000: { sel: "대지면적의 15% 이상", strict: true },
      t1000: { sel: "대지면적의 10% 이상", strict: true },
      tu1000: { sel: "대지면적의 5% 이상" },
    },
  },
];

export const LANDSCAPE_NOTES = [
  "면적 200㎡ 미만 대지는 조경 의무 없음(법 제42조①).",
  "조경 기준은 법이 조례에 위임 — 국가 기준은 시행령 제27조②(공장·물류·소규모) baseline.",
  "면제: 녹지지역, 연면적 1,500㎡ 미만 공장, 축사 등(시행령 제27조①).",
  "옥상조경은 그 면적의 2/3를 대지 조경면적으로 산입(대지 조경면적의 50% 한도, 시행령 제27조③).",
];

// 도시의 tier 목록을 TIER_DEFS 순서로 반환.
export function tiersOf(region) {
  return TIER_DEFS.filter((d) => region.tiers[d.key]).map((d) => ({
    ...d, ...region.tiers[d.key],
  }));
}
