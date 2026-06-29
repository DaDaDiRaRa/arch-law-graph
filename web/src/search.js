// 검색 고도화 — 동의어 확장 + 초성 검색. SearchView 매칭에서 사용.

// ─── 동의어 사전 ───────────────────────────────────────────────────────────
// 각 줄은 서로 동의어인 용어 그룹. 어느 하나로 검색해도 그룹 전체로 확장 매칭.
// 실무 용어 ↔ 법령 표현 격차를 메움. 과도하게 넓히면 결과가 오염되니 보수적으로.
const SYNONYM_GROUPS = [
  ["건폐율", "건축면적의 비율", "대지면적에 대한 건축면적"],
  ["용적률", "연면적의 비율", "대지면적에 대한 연면적"],
  ["일조", "일조권", "정북방향", "채광", "일조등의 확보"],
  ["이격", "대지안의 공지", "대지 안의 공지", "인동간격", "인동거리", "이격거리"],
  ["주차", "부설주차장", "주차장"],
  ["조경", "식재", "조경면적"],
  ["높이제한", "가로구역", "최고높이", "건축물의 높이"],
  ["용도지역", "지역·지구", "지역지구"],
  ["대수선", "수선"],
  ["가설건축물", "가설"],
  ["피난", "직통계단", "피난계단", "피난층"],
  ["방화", "내화", "방화구획", "방화벽"],
  ["증축", "증개축", "개축"],
  ["허가", "건축허가", "인허가"],
  ["위반건축물", "불법건축물", "위반 건축물"],
  ["용도변경", "용도 변경"],
  ["공개공지", "공개 공지", "공개공간"],
  ["완화", "인센티브", "특례"],
  ["심의", "건축위원회", "건축위원회 심의"],
  ["녹색건축", "친환경건축", "제로에너지", "ZEB"],
];

// term(공백제거 소문자) → 동의어 배열 lookup
const SYN = new Map();
for (const grp of SYNONYM_GROUPS) {
  for (const t of grp) {
    SYN.set(t.replace(/\s/g, ""), grp);
  }
}

/** 검색어를 동의어 그룹으로 확장. 매칭은 원문 그대로 비교하므로 그룹 원소를 그대로 반환. */
export function expandTerm(t) {
  const grp = SYN.get(t.replace(/\s/g, ""));
  return grp ? [t, ...grp] : [t];
}

// ─── 초성 검색 ─────────────────────────────────────────────────────────────
const CHO = [
  "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
  "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
];
const CHO_SET = new Set(CHO);

/** 문자열이 초성(자모)으로만 이루어졌는지 — 초성 검색 모드 판별. 2자 이상일 때만. */
export function isChoseong(s) {
  if (!s || s.length < 2) return false;
  for (const ch of s) if (!CHO_SET.has(ch)) return false;
  return true;
}

/**
 * 한글 음절 → 초성 문자열. 비한글(공백·숫자·영문·기호)은 구분자(공백)로 치환.
 * → 초성 검색어(공백 없음)가 단어 경계를 넘어 교차매칭되는 false positive 방지.
 * 예: "건축법 제56조 용적률" → "ㄱㅊㅂ ㅈ ㅈ ㅇㅈㄹ" ('ㅇㅈㄹ'은 '용적률' 안에서만 매칭).
 */
export function choseongOf(text) {
  let out = "";
  for (const ch of text) {
    const code = ch.charCodeAt(0);
    if (code >= 0xac00 && code <= 0xd7a3) {
      out += CHO[Math.floor((code - 0xac00) / 588)];
    } else if (CHO_SET.has(ch)) {
      out += ch;
    } else {
      out += " ";
    }
  }
  return out;
}

/**
 * 단일 검색어 매칭.
 * - 초성어("ㄱㅊㅂ"): textCho(=대상의 초성)에 포함되는지.
 * - 일반어: 동의어 중 하나라도 text 에 포함되는지.
 */
export function matchTerm(t, text, textCho) {
  if (isChoseong(t)) return textCho.includes(t);
  return expandTerm(t).some((s) => text.includes(s));
}
