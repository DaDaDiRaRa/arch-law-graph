// B-6 카드 단일소스화 — 6개 도메인 카드 JS(web/src/*.js)를 평가해 data/standards.json 생성.
//
// 목적: 카드 값(국가 vs 도시 기준 + 근거 조문 refs + src 신뢰도)을 사람 UI(web/src) 밖에서도
//   접근 가능한 데이터 자산으로 노출 → 백엔드 /api/standard·diagnose·MCP 소비. (계획 doc/B-law-api-plan.md)
//
// 방식: (A) 추출/생성물 — JS 모듈이 여전히 1차 소스(SSOT). 이 스크립트는 그것을 평가해 JSON 동기화.
//   incentive 의 items 는 함수 호출(relax/gg/green)로 생성되므로 Node 로 실제 평가해야 정적 JSON 화 가능.
//   (builder/tests/dump_cards.mjs 가 회귀 테스트용으로 같은 평가를 하며, 본 스크립트가 그 6도메인 확장판.)
//
// 결정론: built_at 타임스탬프를 의도적으로 넣지 않음 → 카드 값이 바뀔 때만 파일이 변함
//   (refresh_local.ps1 의 commit-on-change 와 회귀 게이트가 의미있게 동작).
//
// 실행: node builder/gen_standards.mjs   (data/standards.json 기록)

import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { ZONE_DEFS, ZONE_GROUPS, SUNLIGHT_RULE, REGIONS as ZONING_REGIONS } from "../web/src/zoning.js";
import { TIER_DEFS, REGIONS_LS, LANDSCAPE_NOTES } from "../web/src/landscape.js";
import { PARKING_REGIONS } from "../web/src/parking.js";
import { SETBACK_REGIONS } from "../web/src/setback.js";
import { BENEFIT_REGIONS } from "../web/src/incentive.js";
import {
  REVIEW_NATIONAL,
  REVIEW_REGIONS,
  REVIEW_OTHER,
  REVIEW_CROSSLAW,
  REVIEW_NOTES,
} from "../web/src/review.js";

const standards = {
  schema_version: 1,
  // 국가 공통 정의(전국 baseline + 마스터 차원). 도메인 region 값은 여기에 조인된다.
  national: {
    zoning: { zone_defs: ZONE_DEFS, zone_groups: ZONE_GROUPS, sunlight_rule: SUNLIGHT_RULE },
    landscape: { tier_defs: TIER_DEFS, notes: LANDSCAPE_NOTES },
    // parking·setback·incentive 는 각 region row 가 nat(국가)+sel(도시)을 자체 보유 → 별도 national 불필요.
    review: { national: REVIEW_NATIONAL, other: REVIEW_OTHER, crosslaw: REVIEW_CROSSLAW, notes: REVIEW_NOTES },
  },
  // 도메인별 도시 적용값. region.code(2자리 특·광역시 / 5자리 기초시 법정동코드)로 조회.
  // 각 region 은 refs(근거 조문 id 배열) + src(manual/machine/llm) 보존 → 추적가능성·신뢰도 유지.
  domains: {
    zoning: { regions: ZONING_REGIONS },
    landscape: { regions: REGIONS_LS },
    parking: { regions: PARKING_REGIONS },
    setback: { regions: SETBACK_REGIONS },
    incentive: { regions: BENEFIT_REGIONS },
    review: { regions: REVIEW_REGIONS },
  },
};

const json = JSON.stringify(standards, null, 2) + "\n";

// --stdout: 파일을 건드리지 않고 JSON 을 stdout 으로(회귀 게이트 sync 검사용).
if (process.argv.includes("--stdout")) {
  process.stdout.write(json);
} else {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..");
  const outPath = join(root, "data", "standards.json");
  writeFileSync(outPath, json, "utf-8");
  const counts = Object.fromEntries(
    Object.entries(standards.domains).map(([k, v]) => [k, v.regions.length]),
  );
  process.stderr.write(`[standards] wrote ${outPath}\n`);
  process.stderr.write(`[standards] regions: ${JSON.stringify(counts)}\n`);
}
