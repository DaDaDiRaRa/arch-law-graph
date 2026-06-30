// 기준 조회 카드 — 용도지역을 고르면 건폐율·용적률·일조 기준을
// 국가 상한 vs 도시 적용으로 나란히, 모든 수치에 근거 조문 칩.
// zone(def+sel 병합)·refs·regionName 은 SearchView가 선택 도시에 맞춰 주입.
import { nodeById, inRel, lawColor, lawOf, citeIn } from "../data.js";
import { SUNLIGHT_RULE } from "../zoning.js";
import SourceBadge from "./SourceBadge.jsx";
import RefChip from "./RefChip.jsx";

function shortLaw(name = "") {
  return name
    .replace("에 관한 법률", "법")
    .replace("국토의 계획 및 이용", "국토계획")
    .replace("서울특별시 ", "서울 ")
    .replace("부산광역시 ", "부산 ")
    .replace("인천광역시 ", "인천 ")
    .replace(/ /g, "");
}
function refLabel(id) {
  const n = nodeById.get(id);
  if (!n) return id;
  return `${shortLaw(n.law_nm)} ${n.article_no?.startsWith("별표") ? n.article_no : "제" + n.article_no + "조"}`;
}

function RefChips({ refs, onOpen }) {
  return (
    <div className="cc-refs">
      <span className="cc-reflabel">근거</span>
      {refs.map((id) => (
        <RefChip key={id} id={id} label={refLabel(id)} onOpen={onOpen} />
      ))}
    </div>
  );
}

function MetricRow({ label, sub, regionName, nat, sel, unit, note, refs, onOpen }) {
  const stricter = sel < nat;
  return (
    <div className="cc-metric">
      <div className="cc-mlabel"><b>{label}</b>{sub && <span className="cc-msub">{sub}</span>}</div>
      <div className="cc-vals">
        <div className="cc-val">
          <span className="cc-vk">국가 상한</span>
          <span className="cc-vn">{nat}{unit}</span>
        </div>
        <span className="cc-arrow">→</span>
        <div className={"cc-val cc-applied" + (stricter ? " strict" : "")}>
          <span className="cc-vk">{regionName} 적용</span>
          <span className="cc-vn">
            {sel}{unit}
            {note && <em className="cc-vnote">{note}</em>}
          </span>
          {stricter && <span className="cc-badge">조례 강화</span>}
        </div>
      </div>
      <RefChips refs={refs} onOpen={onOpen} />
    </div>
  );
}

function RuleRow({ label, rule, refs, onOpen }) {
  return (
    <div className="cc-metric">
      <div className="cc-mlabel"><b>{label}</b></div>
      <div className="cc-rule">{rule}</div>
      <RefChips refs={refs} onOpen={onOpen} />
    </div>
  );
}

function collectCases(refs) {
  const refIds = [...refs.bcr, ...refs.far, ...refs.sun];
  const seen = new Map();
  for (const rid of refIds) {
    for (const r of inRel.get(rid) || []) {
      if (r.type !== "applied" && r.type !== "interpreted") continue;
      if (!seen.has(r.id)) seen.set(r.id, { id: r.id, type: r.type });
    }
  }
  return [...seen.values()].sort((a, b) => (citeIn.get(b.id) || 0) - (citeIn.get(a.id) || 0));
}

export default function ComplianceCard({ zone, refs, regionName, src, onOpen }) {
  const cases = collectCases(refs);
  return (
    <div className="cc">
      <div className="cc-head">
        <span className="cc-region">{regionName}</span>
        <SourceBadge src={src} />
        <h1>{zone.label}</h1>
        <span className="cc-grp">{zone.group}지역</span>
      </div>

      <MetricRow
        label="건폐율" sub="대지면적 대비 건축면적" regionName={regionName}
        nat={zone.bcrNat} sel={zone.bcr} unit="%" refs={refs.bcr} onOpen={onOpen}
      />
      <MetricRow
        label="용적률" sub="대지면적 대비 연면적" regionName={regionName}
        nat={zone.farNat} sel={zone.far} unit="%" note={zone.farNote} refs={refs.far} onOpen={onOpen}
      />
      {zone.sunlight && (
        <RuleRow label="일조 높이제한" rule={SUNLIGHT_RULE} refs={refs.sun} onOpen={onOpen} />
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
        큐레이션 기준값입니다. 완화·강화·특례(지구단위계획 등)는 근거 조문 원문을 확인하세요.
      </p>
    </div>
  );
}
