import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useChatStream } from "../hooks/useChatStream";
import { ErrorBoundary } from "./ErrorBoundary";
import { MessageBubble } from "./MessageBubble";
import { getChatMode, getShowReasoning } from "../utils/preferences";
import type { ChatMode } from "../utils/preferences";

export function ChatPage() {
  const [chatMode] = useState<ChatMode>(getChatMode);
  const [showReasoning] = useState(getShowReasoning);
  const historyPref = { useServerDefault: true, maxHistoryMessages: 0, enableHistorySummary: false };
  const mcpPref = { useServerDefault: true, enableMcp: true };

  const {
    messages,
    sessionId,
    isStreaming,
    isLoadingHistory,
    historyError,
    sendMessage,
    stopGeneration,
    clearSession,
  } = useChatStream(chatMode, historyPref, mcpPref);

  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-app" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <header className="chat-header">
        <div className="chat-header-brand">
          <h1>AI4S 科研助手</h1>
          <p className="subtitle">{isStreaming ? "生成中…" : "就绪"} · Session: {sessionId.slice(0,8)}</p>
        </div>
        <div className="header-actions">
          <button type="button" className="btn-secondary" onClick={stopGeneration} disabled={!isStreaming}>
            停止
          </button>
          <button type="button" className="btn-secondary" onClick={clearSession} disabled={isStreaming}>
            清空
          </button>
        </div>
      </header>

      {historyError && (
        <div className="history-error" style={{ flexShrink: 0 }}>
          历史加载失败：{historyError}
        </div>
      )}

      <main className="chat-main" ref={listRef} style={{ flex: 1, overflowY: "auto", padding: 20 }}>
        {isLoadingHistory && messages.length === 0 && (
          <div className="history-loading">加载历史…</div>
        )}
        {!isLoadingHistory && messages.length === 0 && (
          <div className="empty-hint">
            <p>输入科研或数学问题开始对话。</p>
          </div>
        )}
        <ErrorBoundary>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} showReasoning={showReasoning} />
          ))}
        </ErrorBoundary>
      </main>

      <footer className="chat-footer" style={{ flexShrink: 0 }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题… Enter 发送"
          rows={2}
          disabled={isStreaming}
        />
        <button
          type="button"
          className="btn-primary"
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
        >
          {isStreaming ? "生成中…" : "发送"}
        </button>
      </footer>
    </div>
  );
}
