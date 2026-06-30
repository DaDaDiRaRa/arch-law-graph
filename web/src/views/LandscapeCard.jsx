// 조경 카드 — 연면적 규모를 고르면 대지 조경면적 기준을
// 국가 baseline vs 도시 적용으로 표시. tier(def+sel)·refs·regionName 은 SearchView 주입.
import { nodeById, inRel, lawColor, lawOf, citeIn } from "../data.js";
import { LANDSCAPE_NOTES } from "../landscape.js";
import SourceBadge from "./SourceBadge.jsx";
import RefChip from "./RefChip.jsx";

function shortLaw(name = "") {
  return name
    .replace("에 관한 법률", "법")
    .replace("서울특별시 건축 조례", "서울 건축조례")
    .replace("부산광역시 건축 조례", "부산 건축조례")
    .replace("인천광역시 건축 조례", "인천 건축조례")
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

export default function LandscapeCard({ tier, refs, regionName, src, onOpen }) {
  const cases = collectCases(refs);
  const applCls = "cc-val cc-applied" + (tier.strict ? " strict" : tier.relax ? " relax" : "");
  return (
    <div className="cc">
      <div className="cc-head">
        <span className="cc-region">{regionName}</span>
        <SourceBadge src={src} />
        <h1 className="cc-h1-sm">{tier.label}</h1>
        <span className="cc-grp">대지의 조경</span>
      </div>

      <div className="cc-metric">
        <div className="cc-mlabel"><b>조경면적 기준</b><span className="cc-msub">대지면적 대비 조경면적</span></div>
        <div className="cc-vals cc-vals-text">
          <div className="cc-val">
            <span className="cc-vk">국가 기준</span>
            <span className="cc-vt">{tier.nat}</span>
          </div>
          <span className="cc-arrow">→</span>
          <div className={applCls}>
            <span className="cc-vk">{regionName} 적용</span>
            <span className="cc-vt">{tier.sel}</span>
            {tier.strict && <span className="cc-badge">조례 강화</span>}
            {tier.relax && <span className="cc-badge cc-badge-relax">조례 완화</span>}
          </div>
        </div>
        <div className="cc-refs">
          <span className="cc-reflabel">근거</span>
          {refs.map((id) => (
            <RefChip key={id} id={id} label={refLabel(id)} onOpen={onOpen} />
          ))}
        </div>
      </div>

      <ul className="cc-notes">
        {LANDSCAPE_NOTES.map((t, i) => <li key={i}>{t}</li>)}
      </ul>

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
        조경면적 산정방법(필로티·온실 등)·면제 세부는 근거 원문을 확인하세요.
      </p>
    </div>
  );
}
