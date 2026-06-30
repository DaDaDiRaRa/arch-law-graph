// 주차 기준 카드 — 건물 용도별 부설주차장 설치기준을 국가 vs 도시로 표시.
// use(nat/sel/strict/note)·refs·regionName 은 SearchView가 선택 도시에 맞춰 주입.
import { nodeById, inRel, lawColor, lawOf, citeIn } from "../data.js";
import SourceBadge from "./SourceBadge.jsx";
import RefChip from "./RefChip.jsx";

function shortLaw(name = "") {
  return name
    .replace("에 관한 법률", "법")
    .replace("서울특별시 주차장 설치 및 관리 조례", "서울 주차조례")
    .replace("부산광역시 주차장 설치 및 관리 조례", "부산 주차조례")
    .replace("인천광역시 주차장 설치 및 관리 조례", "인천 주차조례")
    .replace(/ /g, "");
}
function refLabel(id) {
  const n = nodeById.get(id);
  if (!n) return id;
  const no = n.article_no || "";
  return `${shortLaw(n.law_nm)} ${no.startsWith("별표") ? no : "제" + no + "조"}`;
}

function collectCases(refs) {
  const seen = new Map();
  for (const rid of refs) {
    for (const r of inRel.get(rid) || []) {
      if (r.type !== "applied" && r.type !== "interpreted") continue;
      if (!seen.has(r.id)) seen.set(r.id, { id: r.id, type: r.type });
    }
  }
  return [...seen.values()].sort((a, b) => (citeIn.get(b.id) || 0) - (citeIn.get(a.id) || 0));
}

export default function ParkingCard({ use, refs, regionName, src, onOpen }) {
  const cases = collectCases(refs);
  return (
    <div className="cc">
      <div className="cc-head">
        <span className="cc-region">{regionName}</span>
        <SourceBadge src={src} />
        <h1 className="cc-h1-sm">{use.label}</h1>
        <span className="cc-grp">부설주차장</span>
      </div>

      <div className="cc-metric">
        <div className="cc-mlabel"><b>설치기준</b><span className="cc-msub">시설면적당 주차대수</span></div>
        <div className="cc-vals cc-vals-text">
          <div className="cc-val">
            <span className="cc-vk">국가 기준</span>
            <span className="cc-vt">{use.nat}</span>
          </div>
          <span className="cc-arrow">→</span>
          <div className={"cc-val cc-applied" + (use.strict ? " strict" : "")}>
            <span className="cc-vk">{regionName} 적용</span>
            <span className="cc-vt">{use.sel}</span>
            {use.note && <em className="cc-vnote">{use.note}</em>}
            {use.strict && <span className="cc-badge">조례 강화</span>}
          </div>
        </div>
        <div className="cc-refs">
          <span className="cc-reflabel">근거</span>
          {refs.map((id) => (
            <RefChip key={id} id={id} label={refLabel(id)} onOpen={onOpen} />
          ))}
        </div>
      </div>

      <div className="cc-cases">
        <div className="cc-cases-h"><b>관련 판례·해석례</b> <span>{cases.length}</span></div>
        {cases.length ? (
          <ul>
            {cases.map((c) => {
              const name = lawOf(c.id);
              const short = name.replace(/^(판례|해석례)\s+/, "");
              const n = nodeById.get(c.id);
              return (
                <li key={c.id} onClick={() => onOpen(c.id)}>
                  <span className="cc-ctype" data-t={c.type}>{c.type === "applied" ? "판례" : "해석례"}</span>
                  <span className="cc-cname" style={{ color: lawColor(name) }}>{short}</span>
                  <span className="cc-ctitle">{n?.title}</span>
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="cc-none">연결된 판례·해석례가 아직 없습니다.</div>
        )}
      </div>

      <p className="cc-disc">
        시설면적 = 공용면적 포함 바닥면적 합계(주차시설 면적 제외). 용도 복합·세분·완화는 근거 원문(별표 비고)을 확인하세요.
      </p>
    </div>
  );
}
