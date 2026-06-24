import { useMemo, useState, Fragment } from "react";
import {
  internalLaws,
  articlesByLaw,
  nodeById,
  citeIn,
  lawColor,
  lawOf,
  tier,
  outRel,
  inRel,
  DOMAINS,
} from "../data.js";
import { LawBody, highlightTerms } from "../lib/lawContent.jsx";

const TYPE_LABEL = { references: "참조", cross_law: "타법령", byeolpyo: "별표", delegates: "위임" };

// 검색 문법: "정확구절"  -제외어  나머지는 AND
function parseQuery(raw) {
  const phrases = [], inc = [], exc = [];
  const re = /"([^"]+)"|(\S+)/g;
  let m;
  while ((m = re.exec(raw))) {
    if (m[1]) phrases.push(m[1]);
    else if (m[2].startsWith("-") && m[2].length > 1) exc.push(m[2].slice(1));
    else inc.push(m[2]);
  }
  return { need: [...phrases, ...inc], exc, terms: [...phrases, ...inc] };
}

function shortLaw(name) {
  return name.replace("에 관한 법률", "법").replace("국토의 계획 및 이용", "국토계획").replace(/ /g, "");
}
function artOrder(no = "") {
  const m = /(\d+)(?:의(\d+))?/.exec(no);
  return (no.startsWith("별표") ? 1e6 : 0) + (m ? parseInt(m[1], 10) : 9999) * 100 + (m && m[2] ? +m[2] : 0);
}
function titleOf(a) {
  return a.article_no?.startsWith("별표") ? a.article_no : `제${a.article_no}조`;
}
// 같은 법령군 위계 체인 (법률→시행령→시행규칙)
function familyChain(law) {
  let base = law;
  for (const s of [" 시행규칙", " 시행령"]) if (base.endsWith(s)) base = base.slice(0, -s.length);
  return internalLaws.filter((l) => l === base || l === `${base} 시행령` || l === `${base} 시행규칙`);
}
const ALL = internalLaws.flatMap((law) => articlesByLaw.get(law) || []);
const BM_KEY = "alg.bookmarks";

export default function SearchView() {
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState(null);
  const [selected, setSelected] = useState(null);
  const [bm, setBm] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem(BM_KEY) || "[]")); } catch { return new Set(); }
  });
  const [onlyBm, setOnlyBm] = useState(false);
  const query = q.trim();
  const pq = useMemo(() => parseQuery(query), [query]);

  const toggleBm = (id) =>
    setBm((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      localStorage.setItem(BM_KEY, JSON.stringify([...n]));
      return n;
    });

  // 결과 리스트
  const results = useMemo(() => {
    let pool = ALL;
    if (onlyBm) pool = pool.filter((a) => bm.has(a.id));
    if (domain) pool = pool.filter((a) => (a.domain_tags || []).includes(domain));
    if (!pq.need.length && !pq.exc.length) {
      return [...pool].sort((a, b) => (citeIn.get(b.id) || 0) - (citeIn.get(a.id) || 0)).slice(0, 60);
    }
    const scored = [];
    for (const a of pool) {
      const head = `${a.article_no} ${a.title} ${a.law_nm}`;
      const hay = head + " " + (a.content || "");
      if (pq.exc.some((e) => hay.includes(e))) continue;
      if (!pq.need.every((t) => hay.includes(t))) continue;
      const inHead = pq.need.every((t) => head.includes(t));
      scored.push({ a, rank: inHead ? 0 : 1 });
    }
    scored.sort((x, y) => x.rank - y.rank || (citeIn.get(y.a.id) || 0) - (citeIn.get(x.a.id) || 0));
    return scored.slice(0, 200).map((s) => s.a);
  }, [pq, domain, onlyBm, bm]);

  return (
    <div className="view search-view">
      {/* 검색-우선 진입 */}
      <div className="search-bar">
        <div className="search-wrap">
          <span className="s-ico">🔍</span>
          <input
            autoFocus
            className="g-search"
            placeholder={'검색  ·  "정확한 구절"  ·  -제외어  ·  여러 단어=모두포함'}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {q && <button className="s-clear" onClick={() => setQ("")}>×</button>}
        </div>
        <div className="dchips">
          <button
            className={"dchip star" + (onlyBm ? " on" : "")}
            onClick={() => setOnlyBm((v) => !v)}
            title="즐겨찾기만 보기"
          >
            {onlyBm ? "★" : "☆"} 즐겨찾기 {bm.size > 0 && <b>{bm.size}</b>}
          </button>
          <span className="dsep" />
          <button className={"dchip" + (!domain ? " on" : "")} onClick={() => setDomain(null)}>전체</button>
          {DOMAINS.map((d) => (
            <button key={d} className={"dchip" + (domain === d ? " on" : "")} onClick={() => setDomain(domain === d ? null : d)}>
              {d}
            </button>
          ))}
        </div>
      </div>

      <div className="sv-body">
        {/* 결과 리스트 */}
        <aside className="result-col">
          <div className="rc-head">
            {onlyBm ? "즐겨찾기" : query ? `"${query}" 검색` : domain ? `${domain} 분야` : "영향력 높은 조문"}
            <span>{results.length}{results.length >= 200 ? "+" : ""}</span>
          </div>
          <ul className="result-list">
            {results.map((a) => {
              const cite = citeIn.get(a.id) || 0;
              const marked = bm.has(a.id);
              return (
                <li key={a.id} className={selected?.id === a.id ? "on" : ""} onClick={() => setSelected(a)}>
                  <span className="r-dot" style={{ background: lawColor(a.law_nm) }} />
                  <span className="r-main">
                    <span className="r-no">{titleOf(a)}</span>
                    <span className="r-title">{highlightTerms(a.title || "—", pq.terms)}</span>
                    <span className="r-law">{shortLaw(a.law_nm)}</span>
                  </span>
                  {cite > 0 && <span className="r-cite" title="피인용(영향력)">↩{cite}</span>}
                  <button
                    className={"r-star" + (marked ? " on" : "")}
                    onClick={(e) => { e.stopPropagation(); toggleBm(a.id); }}
                    title="즐겨찾기"
                  >
                    {marked ? "★" : "☆"}
                  </button>
                </li>
              );
            })}
            {results.length === 0 && onlyBm && <li className="r-empty">즐겨찾기한 조문이 없어요.<br />☆를 눌러 추가하세요.</li>}
            {results.length === 0 && !onlyBm && <li className="r-empty">결과 없음</li>}
          </ul>
        </aside>

        {/* 본문 + 근거·관련 조립 */}
        <main className="read-col">
          {selected ? (
            <Reader
              node={selected}
              terms={pq.terms}
              marked={bm.has(selected.id)}
              onStar={() => toggleBm(selected.id)}
              onPick={(id) => { const n = nodeById.get(id); if (n?.type === "article") setSelected(n); }}
              onLaw={(law) => { setQ(law); setDomain(null); setOnlyBm(false); }}
            />
          ) : (
            <div className="empty"><div className="empty-art">🔍</div>왼쪽에서 조문을 고르거나 검색하세요.</div>
          )}
        </main>
      </div>
    </div>
  );
}

// ─── 본문 + 근거 사슬 ────────────────────────────────────────────────────
function Reader({ node, terms, marked, onStar, onPick, onLaw }) {
  const chain = familyChain(node.law_nm);

  const dedupe = (list = []) => {
    const seen = new Map();
    for (const r of list) if (!seen.has(r.id)) seen.set(r.id, r);
    return [...seen.values()].sort((a, b) => tier(lawOf(a.id)) - tier(lawOf(b.id)) || artOrder(nodeById.get(a.id)?.article_no) - artOrder(nodeById.get(b.id)?.article_no));
  };
  const outList = dedupe(outRel.get(node.id));
  const inList = dedupe(inRel.get(node.id));

  return (
    <div className="reader2">
      {/* 법령 위계 체인 */}
      <div className="chain">
        {chain.map((l, i) => (
          <Fragment key={l}>
            {i > 0 && <span className="chain-arr">→</span>}
            <button
              className={"chain-chip" + (l === node.law_nm ? " cur" : "")}
              style={l === node.law_nm ? { borderColor: lawColor(l), color: lawColor(l) } : undefined}
              onClick={() => onLaw(l)}
            >
              {shortLaw(l)}
            </button>
          </Fragment>
        ))}
      </div>

      <div className="r-titlerow">
        <h1>{titleOf(node)} <span>{node.title}</span></h1>
        <button className={"r-bigstar" + (marked ? " on" : "")} onClick={onStar} title="즐겨찾기">
          {marked ? "★" : "☆"}
        </button>
      </div>
      <div className="r-meta">
        {(node.domain_tags || []).map((t) => <span key={t} className="tag">{t}</span>)}
        {node.ef_yd && <span className="meta-dim">시행 {node.ef_yd}</span>}
        {(citeIn.get(node.id) || 0) > 0 && <span className="meta-dim">피인용 {citeIn.get(node.id)}</span>}
      </div>

      <LawBody text={node.content} terms={terms} law={node.law_nm} selfId={node.id} onRef={onPick} onLaw={onLaw} />
      {node.source_url && (
        <a className="link" href={node.source_url} target="_blank" rel="noreferrer">국가법령정보센터 원문 ↗</a>
      )}

      {/* 근거·관련 조립 */}
      <div className="assemble">
        <RelCol title="이 조문이 인용" sub="나가는 근거" list={outList} onPick={onPick} />
        <RelCol title="이 조문을 인용" sub="피인용" list={inList} onPick={onPick} />
      </div>
    </div>
  );
}

function RelCol({ title, sub, list, onPick }) {
  return (
    <div className="rel-col">
      <div className="rel-h"><b>{title}</b> <span>{sub} · {list.length}</span></div>
      {list.length ? (
        <ul>
          {list.map((r) => {
            const n = nodeById.get(r.id);
            const isLaw = n?.type === "law";
            return (
              <li key={r.id} onClick={() => onPick(r.id)}>
                <span className="ty" data-t={r.type}>{TYPE_LABEL[r.type]}</span>
                <span className="rl-law" style={{ color: lawColor(lawOf(r.id)) }}>{shortLaw(lawOf(r.id))}</span>
                <b>{isLaw ? "" : n?.article_no}</b>
                <span className="rl-title">{isLaw ? "(법령)" : n?.title}</span>
              </li>
            );
          })}
        </ul>
      ) : <div className="none">없음</div>}
    </div>
  );
}
