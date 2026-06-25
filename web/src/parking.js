// 부설주차장 설치기준 — 멀티리전(서울·부산·인천) 건물 용도별 큐레이션.
// nat = 국가(주차장법 시행령 별표1), sel = 도시 조례(별표). 모두 graph.json 원문 대조.
//   ※ 부산·인천 별표는 HWP 첨부 → 빌더 HWP 폴백으로 graph.json 에 표 본문 수록.
//   ※ 인천은 도시지역/지구단위 vs 관리지역 2단 기준 → sel=도시지역, note=관리지역.
//   strict = 서울/부산/인천이 국가보다 강화(면적기준↓ = 더 많은 주차).

const PK = "주차장법";
const PK_D = "주차장법 시행령";

const refs = (조례조, 조례별표) => [
  `${PK}/제19조`, `${PK_D}/제6조`, `${PK_D}/별표1`, 조례조, 조례별표,
];

// 국가 기준(시행령 별표1) — 도시 공통 baseline
const NAT = {
  wirak: "시설면적 100㎡당 1대",
  munhwa: "시설면적 150㎡당 1대",
  geunsaeng: "시설면적 200㎡당 1대",
  dandok: "50㎡ 초과~150㎡ 이하: 1대 / 150㎡ 초과: 1+{(면적−150)/100}",
  gongdong: "「주택건설기준 등에 관한 규정」 제27조①에 따라 산정",
  golf: "골프장 1홀 10대 / 골프연습장 1타석 1대 / 옥외수영장 정원 15명당 1대 / 관람장 정원 100명당 1대",
  suryeon: "시설면적 350㎡당 1대",
  changgo: "시설면적 400㎡당 1대",
  etc: "시설면적 300㎡당 1대",
};

export const PARKING_REGIONS = [
  {
    code: "11", name: "서울특별시",
    refs: refs("서울특별시 주차장 설치 및 관리 조례/제20조", "서울특별시 주차장 설치 및 관리 조례/별표2"),
    uses: [
      { key: "wirak", label: "위락시설", nat: NAT.wirak, sel: "시설면적 67㎡당 1대", strict: true },
      { key: "munhwa", label: "문화·집회·종교·판매·운수·의료·운동·방송국·장례식장", nat: NAT.munhwa, sel: "시설면적 100㎡당 1대", strict: true },
      { key: "eopmu", label: "업무시설(외국공관·오피스텔 제외)", nat: NAT.munhwa, sel: "일반업무 100㎡당 1대 / 공공업무 200㎡당 1대", strict: true },
      { key: "geunsaeng", label: "제1·2종 근린생활시설, 숙박시설", nat: NAT.geunsaeng, sel: "시설면적 134㎡당 1대", strict: true },
      { key: "dandok", label: "단독주택(다가구 제외)", nat: NAT.dandok, sel: "국가 기준과 동일", strict: false },
      { key: "gongdong", label: "다가구·공동주택·오피스텔", nat: NAT.gongdong, sel: "좌동 + 세대(호실)당 최소 1대(전용 30㎡↓ 0.5대·60㎡↓ 0.8대)", strict: true },
      { key: "golf", label: "골프장·골프연습장·옥외수영장·관람장", nat: NAT.golf, sel: "국가 기준과 동일", strict: false },
      { key: "suryeon", label: "수련시설·공장(아파트형 제외)·발전시설", nat: NAT.suryeon, sel: "시설면적 233㎡당 1대", strict: true },
      { key: "changgo", label: "창고시설", nat: NAT.changgo, sel: "시설면적 267㎡당 1대", strict: true },
      { key: "etc", label: "그 밖의 건축물", nat: NAT.etc, sel: "200㎡당 1대 (학교 250㎡·학생기숙사 400㎡)", strict: true },
    ],
  },
  {
    code: "26", name: "부산광역시",
    refs: refs("부산광역시 주차장 설치 및 관리 조례/제14조", "부산광역시 주차장 설치 및 관리 조례/별표7"),
    uses: [
      { key: "wirak", label: "위락시설", nat: NAT.wirak, sel: "시설면적 67㎡당 1대", strict: true },
      { key: "munhwa", label: "문화·집회·종교·판매·운수·의료·운동·업무·방송국·장례식장", nat: NAT.munhwa, sel: "시설면적 100㎡당 1대", strict: true },
      { key: "geunsaeng", label: "제1·2종 근린생활시설, 숙박시설", nat: NAT.geunsaeng, sel: "시설면적 134㎡당 1대", strict: true },
      { key: "dandok", label: "단독주택(다가구 제외)", nat: NAT.dandok, sel: "50㎡ 초과~180㎡ 이하: 1대 / 180㎡ 초과: 1+{(면적−180)/120}", strict: false, note: "부산은 기준면적 180㎡·가산 120㎡(국가 150·100과 다름)" },
      { key: "gongdong", label: "다가구·공동주택·오피스텔", nat: NAT.gongdong, sel: "좌동 + 세대당 최소 1대(전용 30㎡↓ 0.5대)", strict: true },
      { key: "golf", label: "골프장·골프연습장·옥외수영장·관람장", nat: NAT.golf, sel: "국가 기준과 동일", strict: false },
      { key: "suryeon", label: "수련시설·공장(아파트형 제외)·발전시설", nat: NAT.suryeon, sel: "시설면적 350㎡당 1대", strict: false },
      { key: "changgo", label: "창고시설", nat: NAT.changgo, sel: "시설면적 400㎡당 1대", strict: false },
      { key: "etc", label: "그 밖의 건축물 (학생기숙사·데이터센터 400㎡)", nat: NAT.etc, sel: "시설면적 200㎡당 1대", strict: true },
    ],
  },
  {
    code: "28", name: "인천광역시",
    refs: refs("인천광역시 주차장 설치 및 관리 조례/제15조", "인천광역시 주차장 설치 및 관리 조례/별표2"),
    note: "인천은 도시지역·지구단위계획구역 / 관리지역 2단 기준. 아래는 도시지역 기준.",
    uses: [
      { key: "wirak", label: "위락시설", nat: NAT.wirak, sel: "시설면적 70㎡당 1대", note: "관리지역 100㎡당 1대", strict: true },
      { key: "munhwa", label: "문화·집회·종교·판매·운수·의료·운동·업무·방송국", nat: NAT.munhwa, sel: "시설면적 100㎡당 1대", note: "관리지역 150㎡당 1대", strict: true },
      { key: "geunsaeng", label: "제1·2종 근린생활시설, 숙박시설", nat: NAT.geunsaeng, sel: "시설면적 134㎡당 1대 (생활숙박은 호실당 1대)", note: "관리지역 200㎡당 1대", strict: true },
      { key: "dandok", label: "단독주택(다가구 제외)", nat: NAT.dandok, sel: "국가 기준과 동일", strict: false },
      { key: "gongdong", label: "다가구·공동주택·오피스텔", nat: NAT.gongdong, sel: "주택건설기준 산정 + 세대당 최소 1대", strict: true },
      { key: "golf", label: "골프장·골프연습장·옥외수영장·관람장", nat: NAT.golf, sel: "골프장 1홀 15대 / 골프연습장 0.7타석당 1대 / 옥외수영장 정원 10명당 1대 / 관람장 정원 70명당 1대", note: "관리지역은 국가 기준과 동일", strict: true },
      { key: "suryeon", label: "수련시설·공장(아파트형 제외)·발전시설", nat: NAT.suryeon, sel: "시설면적 350㎡당 1대", strict: false },
      { key: "changgo", label: "창고시설", nat: NAT.changgo, sel: "시설면적 400㎡당 1대", strict: false },
      { key: "imdae", label: "임대형 기숙사", nat: "—", sel: "시설면적 150㎡당 1대", note: "관리지역 200㎡당 1대", strict: false },
      { key: "etc", label: "그 밖의 건축물 (학생기숙사 350㎡)", nat: NAT.etc, sel: "시설면적 200㎡당 1대", note: "관리지역 300㎡당 1대", strict: true },
    ],
  },
];
