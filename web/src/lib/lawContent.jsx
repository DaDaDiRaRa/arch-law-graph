// 법령/별표 본문 렌더링:
//  - 일반 문단: 제○조 인용 링크 + 검색어 하이라이트
//  - 선문자(┌┐│├┼…) 표: HTML <table> 로 파싱, 실패 시 monospace <pre> 폴백
import { Fragment } from "react";
import { nodeById } from "../data.js";

const RE_REF = /제(\d+)조(?:의(\d+))?/g;
const VBAR = /[│┃]/;
const HBAR = /[─━]/;
const HANGUL = /[가-힣A-Za-z0-9]/;
const JUNC = "┬┴┼┐┘┤├┌└┏┓┗┛┳┻╋┫┣┯┷┠┨╂┿┰┸┝┥╀╁";
const BOXALL = /[─━│┃┌┐└┘├┤┬┴┼┏┓┗┛┣┫┳┻╋┠┨┯┷┿╂┝┥┰┸╀╁╇╈╉╊]/g;

const isBorder = (l) => HBAR.test(l) && !HANGUL.test(l);
const isData = (l) => VBAR.test(l);
const isTableLine = (l) => isBorder(l) || isData(l);

// ── 본문을 표/텍스트 블록으로 분할 ──────────────────────────────────────
// 별표 원문은 표 행 사이에도 빈 줄이 많음 → 표 내부 빈 줄은 무시.
const isBlank = (l) => l.trim() === "";

function parseBlocks(text) {
  const raw = text.split("\n");
  const blocks = [];
  let cur = null;
  const start = (type) => {
    if (cur) blocks.push(cur);
    cur = { type, lines: [] };
  };
  for (let i = 0; i < raw.length; i++) {
    const line = raw[i];
    if (isBlank(line)) {
      let j = i + 1;
      while (j < raw.length && isBlank(raw[j])) j++;
      const nextTable = j < raw.length && isTableLine(raw[j]);
      if (cur && cur.type === "table" && nextTable) continue; // 표 내부 빈 줄 → 버림
      if (!cur || cur.type !== "text") start("text");
      cur.lines.push(line);
      continue;
    }
    const t = isTableLine(line) ? "table" : "text";
    if (!cur || cur.type !== t) start(t);
    cur.lines.push(line);
  }
  if (cur) blocks.push(cur);
  for (const b of blocks) {
    if (b.type === "table") {
      const hasBorder = b.lines.some(isBorder);
      const dataCount = b.lines.filter(isData).length;
      if (!hasBorder || dataCount < 1 || b.lines.length < 3) b.type = "text";
    }
  }
  return blocks;
}

// ── 표시 너비(East Asian Width): 한글·CJK = 2칸 ─────────────────────────
// 박스 표는 "보이는 너비"로 정렬돼 있어 문자열 인덱스가 아닌 표시열로 계산해야 함.
function charW(ch) {
  const c = ch.codePointAt(0);
  if (
    (c >= 0x1100 && c <= 0x115f) ||
    (c >= 0x2e80 && c <= 0xa4cf) ||
    (c >= 0xac00 && c <= 0xd7a3) ||
    (c >= 0xf900 && c <= 0xfaff) ||
    (c >= 0xfe30 && c <= 0xfe4f) ||
    (c >= 0xff00 && c <= 0xff60) ||
    (c >= 0xffe0 && c <= 0xffe6)
  )
    return 2;
  return 1;
}
// 세로선/교차점의 표시열 위치
function sepCols(line, withJunc) {
  const cols = [];
  let dc = 0;
  for (const ch of line) {
    if (VBAR.test(ch) || (withJunc && JUNC.includes(ch))) cols.push(dc);
    dc += charW(ch);
  }
  return cols;
}
// 표시열 (lo, hi) 범위의 문자만 추출
function sliceCols(line, lo, hi) {
  let dc = 0;
  let s = "";
  for (const ch of line) {
    if (dc > lo && dc < hi) s += ch;
    dc += charW(ch);
  }
  return s;
}

// ── 열 경계(세로선) 표시열 위치 추정 ────────────────────────────────────
function colBoundaries(lines) {
  const freq = new Map();
  let n = 0;
  for (const line of lines) {
    if (isBorder(line)) {
      for (const c of sepCols(line, true)) freq.set(c, (freq.get(c) || 0) + 1);
      n++;
    } else if (isData(line)) {
      for (const c of sepCols(line, false)) freq.set(c, (freq.get(c) || 0) + 1);
      n++;
    }
  }
  const thr = Math.max(2, n * 0.4);
  return [...freq.entries()].filter(([, c]) => c >= thr).map(([p]) => p).sort((a, b) => a - b);
}

function parseTable(lines) {
  const bounds = colBoundaries(lines);
  if (bounds.length < 3) return null; // 최소 2열

  // 논리 행 = 경계선 사이의 연속 데이터 행 묶음 (다줄 셀)
  const groups = [];
  let g = [];
  for (const line of lines) {
    if (isBorder(line)) {
      if (g.length) groups.push(g);
      g = [];
    } else if (isData(line)) g.push(line);
  }
  if (g.length) groups.push(g);
  if (groups.length < 1) return null;

  const matrix = groups.map((grp) =>
    bounds.slice(0, -1).map((b, i) => {
      const frag = grp.map((l) => sliceCols(l, b, bounds[i + 1]).replace(BOXALL, "").trim());
      return frag.filter(Boolean).join("").trim(); // 줄바꿈 셀은 이어붙임
    })
  );
  if (matrix[0].length < 2) return null;
  return { header: matrix[0], rows: matrix.slice(1) };
}

// ── 다중 검색어 하이라이트 ──────────────────────────────────────────────
function makeRe(terms) {
  const esc = (terms || []).filter(Boolean).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return esc.length ? new RegExp(`(${esc.join("|")})`, "gi") : null;
}
function pushHi(out, str, re, kref) {
  if (!re) {
    out.push(str);
    return;
  }
  str.split(re).forEach((p, idx) => {
    if (p === "") return;
    if (idx % 2 === 1) out.push(<mark key={`m${kref.k++}`}>{p}</mark>);
    else out.push(<span key={`t${kref.k++}`}>{p}</span>);
  });
}
// 결과 리스트 제목 등에서 쓰는 단순 하이라이트
export function highlightTerms(text, terms) {
  const re = makeRe(terms);
  if (!re) return text;
  return text.split(re).map((p, i) =>
    p === "" ? null : i % 2 === 1 ? <mark key={i}>{p}</mark> : <Fragment key={i}>{p}</Fragment>
  );
}

// 제○조(의○)? (제○항)? 또는 「법령명」
const RE_NAV = /(제\d+조(?:의\d+)?(?:\s*제\d+항)?)|「([^」]+)」/g;

function renderText(text, re, law, selfId, onRef, onLaw) {
  const out = [];
  const kref = { k: 0 };
  let last = 0;
  for (const m of text.matchAll(RE_NAV)) {
    const full = m[0];
    if (m.index > last) pushHi(out, text.slice(last, m.index), re, kref);
    if (m[1]) {
      // 제N조 (같은 법령 내)
      const mm = /제(\d+)조(?:의(\d+))?/.exec(full);
      const tgt = `${law}/제${mm[2] ? `${mm[1]}의${mm[2]}` : mm[1]}조`;
      const mh = /(\s*)(제\d+항)$/.exec(full); // 뒤따르는 제M항
      if (nodeById.has(tgt) && tgt !== selfId) {
        if (mh) {
          // "제49조" 클릭 → 제49조 이동
          out.push(<span key={`r${kref.k++}`} className="ref" onClick={() => onRef(tgt)}>{full.slice(0, full.length - mh[0].length)}</span>);
          if (mh[1]) out.push(mh[1]);
          // "제2항" 클릭 → 같은 제49조 이동, 툴팁에 "제49조 제2항" 표시
          out.push(<span key={`r${kref.k++}`} className="ref" onClick={() => onRef(tgt)} title={full.trim()}>{mh[2]}</span>);
        } else {
          out.push(<span key={`r${kref.k++}`} className="ref" onClick={() => onRef(tgt)}>{full}</span>);
        }
      } else pushHi(out, full, re, kref);
    } else {
      // 「법령명」 — 군 내부 법령이면 이동
      const name = m[2].trim();
      const ln = nodeById.get(name);
      if (ln && ln.type === "law" && !ln.external && onLaw)
        out.push(<span key={`l${kref.k++}`} className="ref" onClick={() => onLaw(name)}>{full}</span>);
      else pushHi(out, full, re, kref);
    }
    last = m.index + full.length;
  }
  if (last < text.length) pushHi(out, text.slice(last), re, kref);
  return out;
}

// 단일열/비격자 박스 → 테두리 프레임 벗기고 본문만
function boxText(lines) {
  return lines
    .filter((l) => !isBorder(l))
    .map((l) => l.replace(/^[\s│┃]+/, "").replace(/[\s│┃]+$/, ""))
    .join("\n")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

// ── 메인 렌더 컴포넌트 ──────────────────────────────────────────────────
export function LawBody({ text, terms, law, selfId, onRef, onLaw }) {
  const clean = (text || "").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n");
  const blocks = parseBlocks(clean);
  const re = makeRe(terms);
  const rt = (s) => renderText(s, re, law, selfId, onRef, onLaw);
  return blocks.map((b, i) => {
    if (b.type === "table") {
      const t = parseTable(b.lines);
      if (t)
        return (
          <div className="bp-tablewrap" key={i}>
            <table className="bp-table">
              <thead>
                <tr>{t.header.map((c, ci) => <th key={ci}>{rt(c)}</th>)}</tr>
              </thead>
              <tbody>
                {t.rows.map((r, ri) => (
                  <tr key={ri}>{r.map((c, ci) => <td key={ci}>{rt(c)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      const bt = boxText(b.lines);
      if (!bt) return null;
      return <pre className="bp-box" key={i}>{rt(bt)}</pre>;
    }
    const body = b.lines.join("\n").replace(/^\n+|\n+$/g, "");
    if (!body.trim()) return null;
    return (
      <p className="content" key={i}>{rt(body)}</p>
    );
  });
}
