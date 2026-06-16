import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useChatStream } from "../hooks/useChatStream";
import {
  getChatMode,
  getEnableHistorySummary,
  getMaxHistoryMessages,
  getShowReasoning,
  getUseServerHistoryDefault,
  setChatMode,
  setEnableHistorySummary,
  setMaxHistoryMessages,
  setShowReasoning,
  setUseServerHistoryDefault,
  type ChatMode,
} from "../utils/preferences";
import { shortSessionId } from "../utils/session";
import { HelpPanel } from "./HelpPanel";
import { MessageBubble } from "./MessageBubble";

export function ChatPage() {
  const [chatMode, setChatModeState] = useState<ChatMode>(getChatMode);
  const [showReasoning, setShowReasoningState] = useState(getShowReasoning);
  const [useServerHistory, setUseServerHistoryState] = useState(getUseServerHistoryDefault);
  const [maxHistoryMessages, setMaxHistoryMessagesState] = useState(getMaxHistoryMessages);
  const [enableHistorySummary, setEnableHistorySummaryState] = useState(getEnableHistorySummary);

  const historyPref = {
    useServerDefault: useServerHistory,
    maxHistoryMessages,
    enableHistorySummary,
  };

  const {
    messages,
    sessionId,
    isStreaming,
    isLoadingHistory,
    historyError,
    activeAgentName,
    sendMessage,
    stopGeneration,
    clearSession,
  } = useChatStream(chatMode, historyPref);
  const [input, setInput] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

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

  const handleModeChange = (mode: ChatMode) => {
    setChatModeState(mode);
    setChatMode(mode);
  };

  const handleShowReasoningChange = (checked: boolean) => {
    setShowReasoningState(checked);
    setShowReasoning(checked);
  };

  const handleUseServerHistoryChange = (checked: boolean) => {
    setUseServerHistoryState(checked);
    setUseServerHistoryDefault(checked);
  };

  const handleMaxHistoryChange = (value: number) => {
    const n = Math.max(0, value);
    setMaxHistoryMessagesState(n);
    setMaxHistoryMessages(n);
    if (n === 0) {
      setEnableHistorySummaryState(false);
      setEnableHistorySummary(false);
    }
  };

  const handleEnableSummaryChange = (checked: boolean) => {
    setEnableHistorySummaryState(checked);
    setEnableHistorySummary(checked);
  };

  return (
    <div className="chat-app">
      <header className="chat-header">
        <div>
          <h1>AI4S 科研助手</h1>
          <p className="subtitle">深度学习损失函数极小值理论 · Phase 2A</p>
        </div>
        <div className="header-actions">
          <span className="session-tag">Session: {shortSessionId(sessionId)}</span>
          {activeAgentName && (
            <span className="session-tag">Agent: {activeAgentName}</span>
          )}
          <div className="mode-toggle" role="group" aria-label="对话模式">
            <button
              type="button"
              className={chatMode === "chat" ? "mode-btn active" : "mode-btn"}
              onClick={() => handleModeChange("chat")}
              disabled={isStreaming}
            >
              Chat
            </button>
            <button
              type="button"
              className={chatMode === "math" ? "mode-btn active" : "mode-btn"}
              onClick={() => handleModeChange("math")}
              disabled={isStreaming}
            >
              Math
            </button>
          </div>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={showReasoning}
              onChange={(e) => handleShowReasoningChange(e.target.checked)}
            />
            思考过程
          </label>
          {isStreaming && (
            <button type="button" className="btn-stop" onClick={stopGeneration}>
              停止
            </button>
          )}
          <button type="button" className="btn-secondary" onClick={() => setHelpOpen(true)}>
            帮助
          </button>
          <button type="button" className="btn-secondary" onClick={clearSession} disabled={isStreaming}>
            清空会话
          </button>
        </div>
      </header>

      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />

      <div className="history-prefs-bar">
        <label className="pref-toggle">
          <input
            type="checkbox"
            checked={useServerHistory}
            onChange={(e) => handleUseServerHistoryChange(e.target.checked)}
            disabled={isStreaming}
          />
          历史策略：服务端默认
        </label>
        <label className="pref-inline">
          保留条数
          <input
            type="number"
            className="history-num-input"
            min={0}
            value={maxHistoryMessages}
            disabled={isStreaming || useServerHistory}
            onChange={(e) => handleMaxHistoryChange(Number(e.target.value))}
            title="0 表示不截断；大于 0 时只向 LLM 发送最近 N 条"
          />
        </label>
        <label className="pref-toggle">
          <input
            type="checkbox"
            checked={enableHistorySummary}
            disabled={isStreaming || useServerHistory || maxHistoryMessages === 0}
            onChange={(e) => handleEnableSummaryChange(e.target.checked)}
          />
          LLM 摘要旧消息
        </label>
      </div>

      {historyError && (
        <div className="history-error">历史加载失败：{historyError}</div>
      )}

      <main className="chat-main" ref={listRef}>
        {isLoadingHistory && (
          <div className="history-loading">加载历史…</div>
        )}
        {!isLoadingHistory && messages.length === 0 && (
          <div className="empty-hint">
            <p>输入科研或数学问题开始对话。</p>
            <p className="hint-examples">
              示例：什么是损失函数的局部极小值？ / 训练 loss 震荡可能有哪些原因？
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} showReasoning={showReasoning} />
        ))}
      </main>

      <footer className="chat-footer">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题… Enter 发送，Shift+Enter 换行"
          rows={2}
          disabled={isStreaming}
        />
        <button type="button" className="btn-primary" onClick={handleSend} disabled={isStreaming || !input.trim()}>
          {isStreaming ? "生成中…" : "发送"}
        </button>
      </footer>
    </div>
  );
}
