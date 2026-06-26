// 건축위원회 심의 대상 체크리스트 카드 — 법정 심의(전국) + 도시 조례 심의(지정·공고 지역).
// region(name·ref·local)·onOpen 은 SearchView 주입. 근거 칩 클릭 → 원문 Reader.
import { nodeById, inRel, lawColor, lawOf, citeIn } from "../data.js";
import { REVIEW_NATIONAL, REVIEW_NOTES } from "../review.js";

function shortLaw(name = "") {
  return name
    .replace("에 관한 법률", "법")
    .replace(/(특별자치시|특별자치도|특별시|광역시)/, "")
    .replace(" 건축 조례", " 건축조례")
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

export default function ReviewCard({ region, onOpen }) {
  const refs = ["건축법/제4의2조", "건축법 시행령/제5의5조", region.ref];
  const cases = collectCases(refs);
  return (
    <div className="cc">
      <div className="cc-head">
        <span className="cc-region">{region.name}</span>
        <h1 className="cc-h1-sm">건축위원회 심의 대상</h1>
        <span className="cc-grp">설계 착수 체크</span>
      </div>

      <div className="cc-metric">
        <div className="cc-mlabel"><b>법정 심의</b><span className="cc-msub">전국 공통 (시행령 제5조의5①)</span></div>
        <ul className="rv-list">
          {REVIEW_NATIONAL.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      </div>

      <div className="cc-metric">
        <div className="cc-mlabel"><b>{region.name} 조례 심의</b><span className="cc-msub">지정·공고 지역 (제5조의5①8호 위임)</span></div>
        <ul className="rv-list rv-local">
          {region.local.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      </div>

      <div className="cc-refs">
        <span className="cc-reflabel">근거</span>
        {refs.map((id) => (
          <button key={id} className="cc-refchip" onClick={() => onOpen(id)} title="원문 조문 열기">
            {refLabel(id)} <span className="cc-go">↗</span>
          </button>
        ))}
      </div>

      <ul className="cc-notes">
        {REVIEW_NOTES.map((t, i) => <li key={i}>{t}</li>)}
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
        규모 경계값·자치구 위원회 관할·심의 생략 요건은 근거 원문을 확인하세요.
      </p>
    </div>
  );
}
