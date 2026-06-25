// 대지 안의 공지(이격거리) 카드 — 건물 용도를 고르면
// 건축선·인접대지경계선 이격거리를 국가 범위(시행령 별표2) vs 서울 적용(건축조례 별표4)으로 표시.
import { nodeById, inRel, lawColor, lawOf, citeIn } from "../data.js";
import { REGION, SETBACK_REFS } from "../setback.js";

function shortLaw(name = "") {
  return name
    .replace("에 관한 법률", "법")
    .replace("서울특별시 건축 조례", "서울 건축조례")
    .replace(/ /g, "");
}
function refLabel(id) {
  const n = nodeById.get(id);
  if (!n) return id;
  const no = n.article_no || "";
  return `${shortLaw(n.law_nm)} ${no.startsWith("별표") ? no : "제" + no + "조"}`;
}

function SbRow({ label, dim }) {
  return (
    <div className="cc-metric">
      <div className="cc-mlabel"><b>{label}</b><span className="cc-msub">띄어야 할 거리</span></div>
      <div className="cc-vals cc-vals-text">
        <div className="cc-val">
          <span className="cc-vk">국가 범위</span>
          <span className="cc-vt">{dim.nat}</span>
        </div>
        <span className="cc-arrow">→</span>
        <div className={"cc-val cc-applied" + (dim.strict ? " strict" : "")}>
          <span className="cc-vk">{REGION.name} 적용</span>
          <span className="cc-vt">{dim.sel}</span>
          {dim.strict && <span className="cc-badge">조례 강화</span>}
        </div>
      </div>
    </div>
  );
}

function collectCases() {
  const seen = new Map();
  for (const rid of SETBACK_REFS) {
    for (const r of inRel.get(rid) || []) {
      if (r.type !== "applied" && r.type !== "interpreted") continue;
      if (!seen.has(r.id)) seen.set(r.id, { id: r.id, type: r.type });
    }
  }
  return [...seen.values()].sort((a, b) => (citeIn.get(b.id) || 0) - (citeIn.get(a.id) || 0));
}

export default function SetbackCard({ use, onOpen }) {
  const cases = collectCases();
  return (
    <div className="cc">
      <div className="cc-head">
        <span className="cc-region">{REGION.name}</span>
        <h1 className="cc-h1-sm">{use.label}</h1>
        <span className="cc-grp">대지 안의 공지</span>
      </div>

      {use.liner && <SbRow label="건축선으로부터" dim={use.liner} />}
      {use.boundary && <SbRow label="인접 대지경계선으로부터" dim={use.boundary} />}
      {use.note && <p className="cc-note">※ {use.note}</p>}

      <div className="cc-refs cc-refs-block">
        <span className="cc-reflabel">근거</span>
        {SETBACK_REFS.map((id) => (
          <button key={id} className="cc-refchip" onClick={() => onOpen(id)} title="원문 조문 열기">
            {refLabel(id)} <span className="cc-go">↗</span>
          </button>
        ))}
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
        건축선/인접경계선 정의·완화·예외는 근거 원문(별표 비고)을 확인하세요. 거리는 건축물 각 부분 기준.
      </p>
    </div>
  );
}
