import { useMemo, useState, Fragment } from "react";
import {
  internalLaws,
  articlesByLaw,
  nodeById,
  citeIn,
  lawColor,
  lawOf,
  familyOf,
  tier,
  outRel,
  inRel,
  DOMAINS,
} from "../data.js";
import { LawBody, highlightTerms } from "../lib/lawContent.jsx";
import ComplianceCard from "./ComplianceCard.jsx";
import ParkingCard from "./ParkingCard.jsx";
import SetbackCard from "./SetbackCard.jsx";
import LandscapeCard from "./LandscapeCard.jsx";
import IncentiveCard from "./IncentiveCard.jsx";
import ReviewCard from "./ReviewCard.jsx";
import ChatPanel from "./ChatPanel.jsx";
import { REGIONS, ZONE_GROUPS, zonesOf } from "../zoning.js";
import { PARKING_REGIONS } from "../parking.js";
import { SETBACK_REGIONS } from "../setback.js";
import { REGIONS_LS, tiersOf } from "../landscape.js";
import { BENEFIT_REGIONS } from "../incentive.js";
import { REVIEW_REGIONS, REVIEW_NATIONAL } from "../review.js";

const TYPE_LABEL = { references: "참조", cross_law: "타법령", byeolpyo: "별표", delegates: "위임", applied: "판례", interpreted: "해석례" };

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
  const no = a.article_no || "";
  // 숫자(제N조/제N조의M)만 '제..조'로. 별표·제N장·전문 등은 그대로.
  return /^\d+(?:의\d+)?$/.test(no) ? `제${no}조` : no;
}
// 같은 법령군 위계 체인 (법률→시행령→시행규칙)
function familyChain(law) {
  let base = law;
  for (const s of [" 시행규칙", " 시행령"]) if (base.endsWith(s)) base = base.slice(0, -s.length);
  return internalLaws.filter((l) => l === base || l === `${base} 시행령` || l === `${base} 시행규칙`);
}
const ALL = internalLaws.flatMap((law) => articlesByLaw.get(law) || []);
const BM_KEY = "alg.bookmarks";

// 문서 종류 — 법령/고시/조례/판례/해석례 (familyOf가 특수 4종은 그대로 반환)
const KINDS = ["법령", "고시", "조례", "판례", "해석례"];
const KIND_COLOR = { 법령: "#4dabf7", 고시: "#7950f2", 조례: "#e64980", 판례: "#343a40", 해석례: "#0c8599" };
const SPECIAL_KIND = new Set(["고시", "조례", "판례", "해석례"]);
function kindOf(lawNm) {
  const f = familyOf(lawNm);
  return SPECIAL_KIND.has(f) ? f : "법령";
}

// 본문 매칭 스니펫 — 첫 매칭어 주변 한 줄 발췌. head(번호·제목·법령)만 걸리면 null.
function snippetOf(content, terms, win = 100) {
  if (!content || !terms.length) return null;
  let idx = -1;
  for (const t of terms) {
    const i = content.indexOf(t);
    if (i >= 0 && (idx < 0 || i < idx)) idx = i;
  }
  if (idx < 0) return null;
  const start = Math.max(0, idx - 30);
  let s = content.slice(start, start + win).replace(/\s+/g, " ").trim();
  if (start > 0) s = "…" + s;
  if (start + win < content.length) s += "…";
  return s;
}

export default function SearchView() {
  const [mode, setMode] = useState("search"); // "search" | "zoning"
  const [region, setRegion] = useState(REGIONS[0]); // 서울·부산·인천
  const [zaxis, setZaxis] = useState("zone"); // "zone" | "parking" | "setback" | "landscape" | "benefit"
  const [zone, setZone] = useState(null);
  const [use, setUse] = useState(null);
  const [sb, setSb] = useState(null);
  const [land, setLand] = useState(null);
  const [benefit, setBenefit] = useState(null);
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState(null);
  const [kind, setKind] = useState(null); // 문서 종류 필터
  const [selected, setSelected] = useState(null);
  const [chatOpen, setChatOpen] = useState(false);
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

  // 결과 리스트 + 종류별 카운트(종류 필터 적용 전 기준)
  const { results, kindCounts } = useMemo(() => {
    let pool = ALL;
    if (onlyBm) pool = pool.filter((a) => bm.has(a.id));
    if (domain) pool = pool.filter((a) => (a.domain_tags || []).includes(domain));

    const empty = !pq.need.length && !pq.exc.length;
    let matched;
    if (empty) {
      matched = [...pool].sort((a, b) => (citeIn.get(b.id) || 0) - (citeIn.get(a.id) || 0));
    } else {
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
      matched = scored.map((s) => s.a);
    }

    const counts = {};
    for (const a of matched) {
      const k = kindOf(a.law_nm);
      counts[k] = (counts[k] || 0) + 1;
    }

    let list = kind ? matched.filter((a) => kindOf(a.law_nm) === kind) : matched;
    list = list.slice(0, empty ? 60 : 200);
    return { results: list, kindCounts: counts };
  }, [pq, domain, onlyBm, bm, kind]);

  // 멀티리전 파생값
  const lsRegion = REGIONS_LS.find((r) => r.code === region.code);
  const pkRegion = PARKING_REGIONS.find((r) => r.code === region.code);
  const sbRegion = SETBACK_REGIONS.find((r) => r.code === region.code);
  const bnRegion = BENEFIT_REGIONS.find((r) => r.code === region.code);
  const rvRegion = REVIEW_REGIONS.find((r) => r.code === region.code);
  const zoneList = useMemo(() => zonesOf(region), [region]);
  const tierList = useMemo(() => (lsRegion ? tiersOf(lsRegion) : []), [lsRegion]);
  const openRef = (id) => { const n = nodeById.get(id); if (n) setSelected(n); };
  const pickRegion = (r) => {
    setRegion(r);
    setZone(null); setLand(null); setUse(null); setSb(null); setBenefit(null); setSelected(null);
  };

  return (
    <div className="view search-view">
      {/* 모드 전환: 검색 ↔ 기준 조회 */}
      <div className="mode-switch">
        <button className={"mode-btn" + (mode === "search" ? " on" : "")} onClick={() => setMode("search")}>
          🔍 검색
        </button>
        <button
          className={"mode-btn" + (mode === "zoning" ? " on" : "")}
          onClick={() => { setMode("zoning"); setSelected(null); }}
        >
          📐 기준 조회
        </button>
      </div>

      {mode === "zoning" ? (
        <>
        {/* 도시 전환 */}
        <div className="region-switch">
          {REGIONS.map((r) => (
            <button key={r.code} className={"region-btn" + (region.code === r.code ? " on" : "")} onClick={() => pickRegion(r)}>
              {r.name}
            </button>
          ))}
        </div>

        {/* 서브축 전환 — 용도지역·조경·완화혜택·심의·이격 17개 지자체, 주차 16개(수원만 보류) */}
        <div className="zaxis-switch">
          <button className={"zaxis-btn" + (zaxis === "zone" ? " on" : "")} onClick={() => { setZaxis("zone"); setSelected(null); }}>
            용도지역 기준
          </button>
          <button className={"zaxis-btn" + (zaxis === "parking" ? " on" : "")} onClick={() => { setZaxis("parking"); setSelected(null); }}>
            주차 기준 (건물 용도)
          </button>
          <button className={"zaxis-btn" + (zaxis === "setback" ? " on" : "")} onClick={() => { setZaxis("setback"); setSelected(null); }}>
            대지 공지 (이격)
          </button>
          <button className={"zaxis-btn" + (zaxis === "landscape" ? " on" : "")} onClick={() => { setZaxis("landscape"); setSelected(null); }}>
            조경
          </button>
          <button className={"zaxis-btn" + (zaxis === "benefit" ? " on" : "")} onClick={() => { setZaxis("benefit"); setSelected(null); }}>
            완화·혜택
          </button>
          <button className={"zaxis-btn" + (zaxis === "review" ? " on" : "")} onClick={() => { setZaxis("review"); setSelected(null); }}>
            심의 대상
          </button>
        </div>

        <div className="sv-body">
          {/* 선택 패널 */}
          <aside className="result-col zone-col">
            {zaxis === "zone" ? (
              <>
                <div className="rc-head">{region.name} · 용도지역<span>{zoneList.length}</span></div>
                <div className="zone-list">
                  {ZONE_GROUPS.filter((g) => zoneList.some((z) => z.group === g)).map((g) => (
                    <div key={g} className="zone-group">
                      <div className="zg-label">{g}지역</div>
                      {zoneList.filter((z) => z.group === g).map((z) => (
                        <button
                          key={z.key}
                          className={"zone-item" + (zone?.key === z.key ? " on" : "")}
                          onClick={() => { setZone(z); setSelected(null); }}
                        >
                          {z.label}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </>
            ) : zaxis === "parking" ? (
              <>
                <div className="rc-head">{region.name} · 건물 용도<span>{pkRegion ? pkRegion.uses.length : 0}</span></div>
                <div className="zone-list">
                  {pkRegion ? pkRegion.uses.map((u) => (
                    <button key={u.key} className={"zone-item" + (use?.key === u.key ? " on" : "")}
                      onClick={() => { setUse(u); setSelected(null); }}>
                      {u.label}
                    </button>
                  )) : <div className="zone-na">데이터 준비 중</div>}
                </div>
              </>
            ) : zaxis === "setback" ? (
              <>
                <div className="rc-head">{region.name} · 건물 용도<span>{sbRegion ? sbRegion.uses.length : 0}</span></div>
                <div className="zone-list">
                  {sbRegion ? sbRegion.uses.map((u) => (
                    <button key={u.key} className={"zone-item" + (sb?.key === u.key ? " on" : "")}
                      onClick={() => { setSb(u); setSelected(null); }}>
                      {u.label}
                    </button>
                  )) : <div className="zone-na">데이터 준비 중</div>}
                </div>
              </>
            ) : zaxis === "landscape" ? (
              <>
                <div className="rc-head">{region.name} · 연면적 규모<span>{tierList.length}</span></div>
                <div className="zone-list">
                  {tierList.map((t) => (
                    <button key={t.key} className={"zone-item" + (land?.key === t.key ? " on" : "")}
                      onClick={() => { setLand(t); setSelected(null); }}>
                      {t.label}
                    </button>
                  ))}
                </div>
              </>
            ) : zaxis === "benefit" ? (
              <>
                <div className="rc-head">{region.name} · 완화·혜택<span>{bnRegion ? bnRegion.items.length : 0}</span></div>
                <div className="zone-list">
                  {bnRegion ? bnRegion.items.map((it) => (
                    <button key={it.key} className={"zone-item" + (benefit?.key === it.key ? " on" : "")}
                      onClick={() => { setBenefit(it); setSelected(null); }}>
                      {it.label}
                    </button>
                  )) : <div className="zone-na">데이터 준비 중</div>}
                </div>
              </>
            ) : (
              <>
                <div className="rc-head">법정 심의<span>전국 공통</span></div>
                <ul className="rv-list" style={{ padding: "8px 14px 20px" }}>
                  {REVIEW_NATIONAL.map((t, i) => <li key={i}>{t}</li>)}
                </ul>
              </>
            )}
          </aside>

          {/* 기준 카드 또는 근거 조문 본문 */}
          <main className="read-col">
            {selected ? (
              <div className="reader2">
                <button className="cc-back" onClick={() => setSelected(null)}>← 기준 카드로</button>
                <Reader
                  node={selected}
                  terms={[]}
                  marked={bm.has(selected.id)}
                  onStar={() => toggleBm(selected.id)}
                  onPick={(id) => { const n = nodeById.get(id); if (n?.type === "article") setSelected(n); }}
                  onLaw={() => {}}
                />
              </div>
            ) : zaxis === "zone" ? (
              zone ? (
                <ComplianceCard zone={zone} refs={region.refs} regionName={region.name} onOpen={openRef} />
              ) : (
                <div className="empty"><div className="empty-art">📐</div>왼쪽에서 용도지역을 고르세요.</div>
              )
            ) : zaxis === "parking" ? (
              !pkRegion ? (
                <div className="empty"><div className="empty-art">🅿️</div>{region.name} 주차 기준은 데이터 준비 중입니다.</div>
              ) : use ? (
                <ParkingCard use={use} refs={pkRegion.refs} regionName={pkRegion.name} onOpen={openRef} />
              ) : (
                <div className="empty"><div className="empty-art">🅿️</div>왼쪽에서 건물 용도를 고르세요.</div>
              )
            ) : zaxis === "setback" ? (
              !sbRegion ? (
                <div className="empty"><div className="empty-art">📏</div>{region.name} 대지 공지(이격) 기준은 데이터 준비 중입니다.</div>
              ) : sb ? (
                <SetbackCard use={sb} refs={sbRegion.refs} regionName={sbRegion.name} onOpen={openRef} />
              ) : (
                <div className="empty"><div className="empty-art">📏</div>왼쪽에서 건물 용도를 고르세요.</div>
              )
            ) : zaxis === "landscape" ? (
              land ? (
                <LandscapeCard tier={land} refs={lsRegion.refs} regionName={lsRegion.name} onOpen={openRef} />
              ) : (
                <div className="empty"><div className="empty-art">🌳</div>왼쪽에서 연면적 규모를 고르세요.</div>
              )
            ) : zaxis === "benefit" ? (
              !bnRegion ? (
                <div className="empty"><div className="empty-art">🎁</div>{region.name} 완화·혜택은 데이터 준비 중입니다.</div>
              ) : benefit ? (
                <IncentiveCard item={benefit} regionName={bnRegion.name} onOpen={openRef} />
              ) : (
                <div className="empty"><div className="empty-art">🎁</div>왼쪽에서 항목(공개공지·주차 면제)을 고르세요.</div>
              )
            ) : !rvRegion ? (
              <div className="empty"><div className="empty-art">📋</div>{region.name} 심의 대상은 데이터 준비 중입니다.</div>
            ) : (
              <ReviewCard region={rvRegion} onOpen={openRef} />
            )}
          </main>
        </div>
        </>
      ) : (
      <>
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
        {/* 종류 필터 — 법령/고시/조례/판례/해석례 (결과에 존재하는 종류만) */}
        <div className="kchips">
          <button className={"kchip" + (!kind ? " on" : "")} onClick={() => setKind(null)}>전체</button>
          {KINDS.filter((k) => kindCounts[k]).map((k) => (
            <button
              key={k}
              className={"kchip k-" + k + (kind === k ? " on" : "")}
              onClick={() => setKind(kind === k ? null : k)}
            >
              <span className="kdot" style={{ background: KIND_COLOR[k] }} />
              {k} <b>{kindCounts[k]}</b>
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
              const snip = query ? snippetOf(a.content, pq.terms) : null;
              return (
                <li key={a.id} className={selected?.id === a.id ? "on" : ""} onClick={() => setSelected(a)}>
                  <span className="r-dot" style={{ background: lawColor(a.law_nm) }} />
                  <span className="r-main">
                    <span className="r-no">{titleOf(a)}</span>
                    <span className="r-title">{highlightTerms(a.title || "—", pq.terms)}</span>
                    {snip && <span className="r-snip">{highlightTerms(snip, pq.terms)}</span>}
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
      </>
      )}

      {/* ─── 플로팅 AI 채팅 버튼 ─── */}
      <button
        className={"chat-fab" + (chatOpen ? " open" : "")}
        onClick={() => setChatOpen((v) => !v)}
        title="AI 법령 질의"
      >
        {chatOpen ? "✕" : "💬"}
      </button>

      <ChatPanel
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        selectedNode={selected}
        onOpenRef={(id) => {
          const n = nodeById.get(id);
          if (!n) return;
          if (mode !== "search") setMode("search");
          setSelected(n);
        }}
      />
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
