// 대지 안의 공지(이격거리) — 멀티리전(서울·부산·인천) 건물 용도별 큐레이션.
// 두 축: ① 건축선(liner) ② 인접 대지경계선(boundary). nat=시행령 별표2(범위), sel=도시 조례 별표.
//   ※ 부산·인천 별표는 HWP 첨부 → 빌더 HWP 폴백으로 graph.json 수록.
//   strict = 도시가 국가 범위 하한을 구체화/강화.

const L_ARCH = "건축법";
const L_ARCH_D = "건축법 시행령";

const refs = (조례조, 조례별표) => [
  `${L_ARCH}/제58조`, `${L_ARCH_D}/제80의2조`, `${L_ARCH_D}/별표2`, 조례조, 조례별표,
];

// 국가 baseline (시행령 별표2) — 도시 공통
const NAT = {
  gongdong_l: "아파트 2~6m / 연립 2~5m / 다세대 1~4m",
  gongdong_b: "아파트 2~6m / 연립 1.5~5m / 다세대 0.5~4m",
  jeonju_b: "1~6m (한옥 처마선 2m↓·외벽선 1~2m)",
  panmae_l: "1,000㎡↑: 3~6m",
  panmae_b: "1,000㎡↑(상업지역 아닌 곳): 1.5~6m",
  gongjang_l: "준공업 1.5~6m / 그 외 3~6m",
  gongjang_b: "준공업 1~6m / 그 외 1.5~6m",
  etc_l: "1~6m (한옥 처마선 2m↓·외벽선 1~2m)",
  etc_b: "0.5~6m (한옥 처마선 2m↓·외벽선 1~2m)",
};

export const SETBACK_REGIONS = [
  {
    code: "11", name: "서울특별시",
    refs: refs("서울특별시 건축 조례/제30조", "서울특별시 건축 조례/별표4"),
    uses: [
      { key: "gongdong", label: "공동주택", note: "상업지역+자동식소화설비 공동주택은 인접경계 제외",
        liner: { nat: NAT.gongdong_l, sel: "아파트 3m↑ (도시형 아파트형 2m↑) / 연립 2m↑ / 다세대 1m↑", strict: true },
        boundary: { nat: NAT.gongdong_b, sel: "아파트 3m↑ / 연립 1.5m↑ / 다세대 1m↑", strict: true } },
      { key: "jeonju", label: "전용주거지역 건축물(공동주택 제외)",
        boundary: { nat: NAT.jeonju_b, sel: "1m↑", strict: false } },
      { key: "panmae", label: "판매·숙박·문화집회·종교시설 등 (대규모)", note: "일반숙박·전시장·동식물원 제외",
        liner: { nat: NAT.panmae_l, sel: "1,000㎡↑ 3m↑ / 1,000㎡ 미만(문화집회·종교·장례식장) 1m↑", strict: true },
        boundary: { nat: NAT.panmae_b, sel: "1,000㎡↑ 1.5m↑ / 1,000㎡ 미만 1m↑ (상업지역 제외)", strict: true } },
      { key: "gongjang", label: "공장·창고 (바닥면적 500㎡↑)", note: "전용·일반공업·산업단지 제외",
        liner: { nat: NAT.gongjang_l, sel: "준공업 1.5m↑ / 그 외 3m↑", strict: true },
        boundary: { nat: NAT.gongjang_b, sel: "준공업 1m↑ / 그 외 1.5m↑", strict: true } },
      { key: "etc", label: "그 밖의 건축물",
        liner: { nat: NAT.etc_l, sel: "조례 별표4 해당 항목 확인", strict: false },
        boundary: { nat: NAT.etc_b, sel: "조례 별표4 해당 항목 확인", strict: false } },
    ],
  },
  {
    code: "26", name: "부산광역시",
    refs: refs("부산광역시 건축 조례/제39의2조", "부산광역시 건축 조례/별표4"),
    uses: [
      { key: "gongdong", label: "공동주택",
        liner: { nat: NAT.gongdong_l, sel: "아파트 3m↑ / 연립 2m↑ / 다세대 1m↑", strict: true },
        boundary: { nat: NAT.gongdong_b, sel: "아파트 3m↑ (도시형 2m↑) / 연립 1.5m↑ / 다세대 1m↑ (도시형 0.5m↑)", strict: true } },
      { key: "jeonju", label: "전용주거지역 건축물(공동주택 제외)",
        boundary: { nat: NAT.jeonju_b, sel: "1m↑", strict: false } },
      { key: "panmae", label: "판매·숙박·문화집회·종교·의료·운수·장례식장 (1,000㎡↑)", note: "일반숙박·전시장·동식물원 제외",
        liner: { nat: NAT.panmae_l, sel: "3m↑", strict: true },
        boundary: { nat: NAT.panmae_b, sel: "1.5m↑ (상업지역 제외)", strict: true } },
      { key: "gongjang", label: "공장·창고 (바닥면적 500㎡↑)", note: "전용·일반공업·산업단지 제외",
        liner: { nat: NAT.gongjang_l, sel: "준공업 1.5m↑ / 그 외 3m↑", strict: true },
        boundary: { nat: NAT.gongjang_b, sel: "준공업 1m↑ / 그 외 1.5m↑", strict: true } },
      { key: "wirum", label: "위험물 저장·처리시설 (200㎡↑)",
        liner: { nat: NAT.etc_l, sel: "준공업 1m↑ / 그 외 1.5m↑", strict: true },
        boundary: { nat: NAT.etc_b, sel: "준공업 1m↑ / 그 외 1.5m↑", strict: true } },
    ],
  },
  {
    code: "28", name: "인천광역시",
    refs: refs("인천광역시 건축 조례/제27조", "인천광역시 건축 조례/별표2"),
    uses: [
      { key: "gongdong", label: "공동주택", note: "상업지역+자동식소화설비 공동주택은 인접경계 제외",
        liner: { nat: NAT.gongdong_l, sel: "아파트 6m↑ (도시형·리모델링·정비 아파트 3m↑) / 연립 2m↑ / 다세대 1m↑", strict: true },
        boundary: { nat: NAT.gongdong_b, sel: "아파트 3m↑ (도시형 2m↑) / 연립 1.5m↑ / 다세대 1m↑", strict: true } },
      { key: "jeonju", label: "전용주거지역 건축물(공동주택 제외)",
        boundary: { nat: NAT.jeonju_b, sel: "1m↑", strict: false } },
      { key: "panmae", label: "판매·숙박·문화집회·종교·운수·의료(종합병원)·장례식장 (1,000㎡↑)", note: "일반숙박·전시장·동식물원 제외",
        liner: { nat: NAT.panmae_l, sel: "3m↑", strict: true },
        boundary: { nat: NAT.panmae_b, sel: "1.5m↑ (상업지역 제외)", strict: true } },
      { key: "gongjang", label: "공장·창고 (바닥면적 500㎡↑)", note: "전용·일반공업·산업단지 제외",
        liner: { nat: NAT.gongjang_l, sel: "준공업 1.5m↑ / 기타 지역 3m↑", strict: true },
        boundary: { nat: NAT.gongjang_b, sel: "준공업 1m↑ / 기타 지역 1.5m↑", strict: true } },
      { key: "etc", label: "그 밖의 건축물 (자동차관련 500㎡↑·위험물·한옥 등)",
        liner: { nat: NAT.etc_l, sel: "자동차관련·위험물 3m↑ / 한옥 처마선 1m↑·외벽선 2m↑", strict: true },
        boundary: { nat: NAT.etc_b, sel: "1m↑ / 한옥 처마선 0.5m↑·외벽선 2m↑", strict: true } },
    ],
  },
];
