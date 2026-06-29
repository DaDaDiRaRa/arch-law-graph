// 완화·혜택 카드 — 공개공지 / 부설주차 면제·완화를 국가 vs 도시 적용으로 표시.
// item(label·rows·refs·notes)·regionName 은 SearchView 주입. rows = [{label,nat,sel,strict?}].
import { nodeById, inRel, lawColor, lawOf, citeIn } from "../data.js";
import SourceBadge from "./SourceBadge.jsx";

function shortLaw(name = "") {
  return name
    .replace("에 관한 법률", "법")
    .replace(/(특별자치시|특별자치도|특별시|광역시)/, "")
    .replace(" 건축 조례", " 건축조례")
    .replace(" 도시계획 조례", " 도시계획조례")
    .replace(" 주차장 설치 및 관리 조례", " 주차조례")
    .replace(" 주차장 조례", " 주차조례")
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

export default function IncentiveCard({ item, regionName, src, onOpen }) {
  const cases = collectCases(item.refs);
  return (
    <div className="cc">
      <div className="cc-head">
        <span className="cc-region">{regionName}</span>
        <SourceBadge src={src} />
        <h1 className="cc-h1-sm">{item.label}</h1>
        <span className="cc-grp">완화·혜택</span>
      </div>

      {item.rows.map((row, i) => (
        <div className="cc-metric" key={i}>
          <div className="cc-mlabel"><b>{row.label}</b></div>
          <div className="cc-vals cc-vals-text">
            <div className="cc-val">
              <span className="cc-vk">국가 기준</span>
              <span className="cc-vt">{row.nat}</span>
            </div>
            <span className="cc-arrow">→</span>
            <div className={"cc-val cc-applied" + (row.strict ? " strict" : "")}>
              <span className="cc-vk">{regionName} 적용</span>
              <span className="cc-vt">{row.sel}</span>
              {row.strict && <span className="cc-badge">조례 강화</span>}
            </div>
          </div>
        </div>
      ))}

      <div className="cc-refs">
        <span className="cc-reflabel">근거</span>
        {item.refs.map((id) => (
          <button key={id} className="cc-refchip" onClick={() => onOpen(id)} title="원문 조문 열기">
            {refLabel(id)} <span className="cc-go">↗</span>
          </button>
        ))}
      </div>

      {item.notes?.length > 0 && (
        <ul className="cc-notes">
          {item.notes.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      )}

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
        면적 산정(필로티·지하)·완화 산식·면제 세부 요건은 근거 원문을 확인하세요.
      </p>
    </div>
  );
}
