// 근거 조문 칩 — 6개 기준 카드 공유 (C-3 시행일 전파).
// label 은 카드별 refLabel 결과를 주입(법령명 단축 규칙이 카드마다 달라 라벨은 외부 생성).
// 칩에 조문 시행일을 함께 노출해 "현행 조문인가"를 카드 단위에서 보장.
import { efDate } from "../data.js";

export default function RefChip({ id, label, onOpen, className = "" }) {
  const ef = efDate(id);
  return (
    <button
      className={"cc-refchip" + (className ? " " + className : "")}
      onClick={() => onOpen(id)}
      title={ef ? `시행 ${ef} · 원문 조문 열기` : "원문 조문 열기"}
    >
      {label} <span className="cc-go">↗</span>
      {ef && <span className="cc-ef">시행 {ef}</span>}
    </button>
  );
}
