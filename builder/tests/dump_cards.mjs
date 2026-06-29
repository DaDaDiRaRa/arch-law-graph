// LLM 보조 카드(주차·이격·심의·완화)의 실제 렌더 데이터를 JSON 으로 덤프.
// incentive 의 items 는 함수 호출(relax/gg/green)로 생성되므로 정규식 파싱 불가 → Node 로 실제 평가.
// pytest(test_llm_cards.py)가 이 출력을 골든 스냅샷과 대조한다.
//
// 실행: node builder/tests/dump_cards.mjs   (stdout 에 JSON)
import { PARKING_REGIONS } from "../../web/src/parking.js";
import { SETBACK_REGIONS } from "../../web/src/setback.js";
import { REVIEW_REGIONS, REVIEW_NATIONAL } from "../../web/src/review.js";
import { BENEFIT_REGIONS } from "../../web/src/incentive.js";

const out = {
  parking: PARKING_REGIONS,
  setback: SETBACK_REGIONS,
  review: { national: REVIEW_NATIONAL, regions: REVIEW_REGIONS },
  incentive: BENEFIT_REGIONS,
};
process.stdout.write(JSON.stringify(out));
