// 값별 출처·신뢰도 배지 (C-2) — 카드 데이터가 어떻게 만들어졌는지 표시.
// src 는 카드 데이터 모듈(zoning/parking/…)의 region 객체에 태깅됨(손큐=manual, 기계추출=machine, LLM보조=llm).
const SRC_META = {
  manual: { label: "손큐레이션", title: "사람이 법령 원문과 대조해 직접 입력 — 최고 신뢰도" },
  machine: { label: "기계추출", title: "조례 본문에서 정규식으로 자동추출(무해석). 회귀 스냅샷 테스트로 검증." },
  llm: { label: "LLM보조", title: "LLM(claude temp0)이 별표·조문에서 추출, 손큐레이션 대조로 환각 검증. 원문 근거 칩으로 추적 가능." },
};

export default function SourceBadge({ src }) {
  const m = SRC_META[src];
  if (!m) return null;
  return (
    <span className={`src-badge src-${src}`} title={m.title}>
      {m.label}
    </span>
  );
}
