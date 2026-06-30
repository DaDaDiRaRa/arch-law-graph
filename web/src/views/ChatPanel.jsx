import { useState, useRef, useEffect } from "react";
import { nodeById, efDate } from "../data.js";

const EXAMPLES = [
  "제2종일반주거지역 건폐율·용적률 기준과 예외 조건",
  "근린생활시설 주차 면제 기준이 어떻게 되나요",
  "일조권 사선제한 적용 요건과 예외 설명해줘",
  "건축물 높이 제한 관련 조문 종합해서 알려줘",
];

function shortLawName(nm = "") {
  return nm
    .replace("에 관한 법률", "법")
    .replace("국토의 계획 및 이용", "국토계획")
    .slice(0, 14);
}

// source_ids → { "법령명 제N조": id, "단축명 제N조": id, ... }
function buildRefMap(sourceIds) {
  const map = {};
  for (const id of sourceIds || []) {
    const n = nodeById.get(id);
    if (!n?.article_no) continue;
    const no = n.article_no;
    // rag_engine.py 의 _fmt 와 동일 형식: 숫자시작이면 "제N조"
    const label = /^\d/.test(no) ? `제${no}조` : no;
    for (const lawLabel of [n.law_nm, shortLawName(n.law_nm)]) {
      if (!lawLabel) continue;
      const key = `${lawLabel} ${label}`;
      if (key && !map[key]) map[key] = id;
      // "법령명 제N조의M" 변형도 처리 (예: 제84조의2)
      if (/의\d/.test(no)) {
        const [base, sub] = no.split("의");
        const altLabel = `제${base}조의${sub}`;
        const altKey = `${lawLabel} ${altLabel}`;
        if (!map[altKey]) map[altKey] = id;
      }
    }
  }
  return map;
}

// 답변 텍스트를 파싱해 조문 참조를 클릭 가능한 버튼으로 렌더링
function renderAnswerText(text, sourceIds, onOpenRef) {
  if (!text) return null;

  const refMap = buildRefMap(sourceIds);
  const keys = Object.keys(refMap).sort((a, b) => b.length - a.length);

  if (!keys.length) return <>{text}</>;

  const escaped = keys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`(${escaped.join("|")})`, "g");
  const parts = text.split(re);

  return parts.map((part, i) => {
    const id = refMap[part];
    if (id) {
      const ef = efDate(id);
      return (
        <button key={i} className="answer-ref" onClick={() => onOpenRef(id)} title={ef ? `시행 ${ef}` : id}>
          {part}↗
        </button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function ChatPanel({ selectedNode, onOpenRef, open, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [ctxPinned, setCtxPinned] = useState(true);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // selectedNode가 바뀌면(새 조문 열기) 핀을 자동 복원
  const prevNodeId = useRef(null);
  useEffect(() => {
    if (selectedNode?.id && selectedNode.id !== prevNodeId.current) {
      setCtxPinned(true);
      prevNodeId.current = selectedNode.id;
    }
  }, [selectedNode?.id]);

  const effectiveSelectedId = ctxPinned && selectedNode ? selectedNode.id : null;

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text) {
    const question = (text || input).trim();
    if (!question || loading) return;
    setInput("");
    setLoading(true);

    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", source_ids: [], loading: true },
    ]);

    let accText = "";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, selected_id: effectiveSelectedId }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const chunk = JSON.parse(line.slice(6));
            if (chunk.type === "token") {
              accText += chunk.content;
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = { ...next[next.length - 1], content: accText };
                return next;
              });
            } else if (chunk.type === "done") {
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = {
                  ...next[next.length - 1],
                  source_ids: chunk.source_ids || [],
                  unverified: chunk.unverified || [],
                  loading: false,
                };
                return next;
              });
            }
          } catch (_) {}
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          ...next[next.length - 1],
          content: `오류가 발생했습니다. 백엔드가 실행 중인지 확인하세요.\n(${err.message})`,
          loading: false,
        };
        return next;
      });
    }

    setLoading(false);
  }

  if (!open) return null;

  // 사이드 드로어 — overlay backdrop 없음, 뒤쪽 Reader 스크롤·클릭 가능
  return (
    <div className="chat-panel">
      {/* 헤더 */}
      <div className="chat-header">
        <span className="chat-title">💬 AI 법령 질의</span>
        {selectedNode && (
          <button
            className={`chat-ctx-badge${ctxPinned ? "" : " unpinned"}`}
            onClick={() => setCtxPinned((v) => !v)}
            title={ctxPinned
              ? "클릭하면 전체 법령 기준으로 검색합니다"
              : "클릭하면 이 조문을 컨텍스트로 고정합니다"}
          >
            {ctxPinned ? "📌" : "🔍"}&nbsp;
            {ctxPinned
              ? `${shortLawName(selectedNode.law_nm)}${selectedNode.article_no ? ` 제${selectedNode.article_no}조` : ""}`
              : "전체 법령"}
          </button>
        )}
        <button className="chat-close" onClick={onClose} title="닫기">✕</button>
      </div>

      {/* 메시지 목록 */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-hint">
            <p className="chat-hint-lead">건축법규 관련 질문을 자유롭게 물어보세요.</p>
            <div className="chat-examples">
              {EXAMPLES.map((ex) => (
                <button key={ex} className="chat-ex-btn" onClick={() => send(ex)}>
                  {ex}
                </button>
              ))}
            </div>
            {selectedNode && (
              <p className="chat-hint-ctx">
                {ctxPinned ? (
                  <>
                    현재&nbsp;
                    <b>
                      {shortLawName(selectedNode.law_nm)}
                      {selectedNode.article_no ? ` 제${selectedNode.article_no}조` : ""}
                    </b>
                    가 컨텍스트로 자동 포함됩니다.&nbsp;
                    <button className="ctx-pin-link" onClick={() => setCtxPinned(false)}>전체 법령으로 변경</button>
                  </>
                ) : (
                  <>
                    전체 법령을 기준으로 검색합니다.&nbsp;
                    <button className="ctx-pin-link" onClick={() => setCtxPinned(true)}>📌 조문 고정</button>
                  </>
                )}
              </p>
            )}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-${m.role}`}>
            {m.role === "user" ? (
              <div className="chat-bubble chat-bubble-user">{m.content}</div>
            ) : (
              <div className="chat-bubble chat-bubble-ai">
                <div className="chat-text">
                  {m.loading ? (
                    // 스트리밍 중: 평문 + 커서
                    <>
                      {m.content}
                      <span className="chat-cursor">▋</span>
                    </>
                  ) : (
                    // 완료: 조문 참조를 클릭 가능 링크로 렌더링
                    renderAnswerText(m.content, m.source_ids, onOpenRef)
                  )}
                </div>

                {/* 인용 검증 경고 — DB에 실재하지 않는 '법령명 제N조' (환각 가능) */}
                {!m.loading && m.unverified?.length > 0 && (
                  <div className="chat-unverified" role="alert">
                    <span className="cu-icon">⚠</span>
                    <span className="cu-text">
                      DB에서 확인되지 않은 인용 — 원문 확인 요망:{" "}
                      {m.unverified.map((c, i) => (
                        <span key={i} className="cu-cite">{c}</span>
                      ))}
                    </span>
                  </div>
                )}

                {/* 하단 출처 칩 (빠른 전체 목록) */}
                {!m.loading && m.source_ids?.length > 0 && (
                  <div className="chat-sources">
                    <span className="chat-src-label">근거 조문</span>
                    {m.source_ids.slice(0, 10).map((id) => {
                      const n = nodeById.get(id);
                      if (!n) return null;
                      const label = n.article_no
                        ? `${shortLawName(n.law_nm)} 제${n.article_no}조`
                        : shortLawName(n.law_nm);
                      const ef = efDate(id);
                      return (
                        <button
                          key={id}
                          className="chat-src-chip"
                          onClick={() => onOpenRef(id)}
                          title={ef ? `시행 ${ef}` : id}
                        >
                          {label}
                          {ef && <span className="cc-ef">시행 {ef}</span>}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 입력 */}
      <div className="chat-input-row">
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="질문 입력 후 Enter (줄바꿈: Shift+Enter)"
          rows={2}
          disabled={loading}
        />
        <button
          className="chat-send"
          onClick={() => send()}
          disabled={loading || !input.trim()}
        >
          {loading ? "…" : "전송"}
        </button>
      </div>
    </div>
  );
}
