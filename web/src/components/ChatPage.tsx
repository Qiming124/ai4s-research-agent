import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useChatStream } from "../hooks/useChatStream";
import { useMcpStatus } from "../hooks/useMcpStatus";
import { waitForBackend } from "../utils/backend";
import {
  getChatMode,
  getEnableHistorySummary,
  getEnableMcp,
  getMaxHistoryMessages,
  getShowReasoning,
  getUseServerHistoryDefault,
  getUseServerMcpDefault,
  setChatMode,
  setEnableHistorySummary,
  setEnableMcp,
  setMaxHistoryMessages,
  setShowReasoning,
  setUseServerHistoryDefault,
  setUseServerMcpDefault,
  type ChatMode,
} from "../utils/preferences";
import { shortSessionId } from "../utils/session";
import { AgentSettingsSidebar } from "./AgentSettingsSidebar";
import { ErrorBoundary } from "./ErrorBoundary";
import { HelpPanel } from "./HelpPanel";
import { MessageBubble } from "./MessageBubble";

export function ChatPage() {
  const [chatMode, setChatModeState] = useState<ChatMode>(getChatMode);
  const [showReasoning, setShowReasoningState] = useState(getShowReasoning);
  const [useServerHistory, setUseServerHistoryState] = useState(getUseServerHistoryDefault);
  const [maxHistoryMessages, setMaxHistoryMessagesState] = useState(getMaxHistoryMessages);
  const [enableHistorySummary, setEnableHistorySummaryState] = useState(getEnableHistorySummary);
  const [useServerMcp, setUseServerMcpState] = useState(getUseServerMcpDefault);
  const [enableMcp, setEnableMcpState] = useState(getEnableMcp);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const historyPref = {
    useServerDefault: useServerHistory,
    maxHistoryMessages,
    enableHistorySummary,
  };

  const mcpPref = {
    useServerDefault: useServerMcp,
    enableMcp,
  };

  const {
    status: mcpStatus,
    loading: mcpLoading,
    error: mcpError,
    refresh: refreshMcp,
  } = useMcpStatus();

  const {
    messages,
    sessionId,
    isStreaming,
    isLoadingHistory,
    historyError,
    backendOffline,
    activeAgentName,
    activeToolName,
    sendMessage,
    stopGeneration,
    clearSession,
    reloadHistory,
  } = useChatStream(chatMode, historyPref, mcpPref);
  const [input, setInput] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [retryingBackend, setRetryingBackend] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (settingsOpen) {
      refreshMcp();
    }
  }, [settingsOpen, refreshMcp]);

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

  const handleUseServerMcpChange = (checked: boolean) => {
    setUseServerMcpState(checked);
    setUseServerMcpDefault(checked);
  };

  const handleEnableMcpChange = (checked: boolean) => {
    setEnableMcpState(checked);
    setEnableMcp(checked);
  };

  const handleRetryBackend = async () => {
    setRetryingBackend(true);
    try {
      const ready = await waitForBackend(5, 1000);
      if (ready) {
        await refreshMcp();
        await reloadHistory({ force: true });
      }
    } finally {
      setRetryingBackend(false);
    }
  };

  return (
    <div className="chat-app">
      <header className="chat-header">
        <div>
          <h1>AI4S 科研助手</h1>
          <p className="subtitle">深度学习损失函数极小值理论 · Phase 2A/2B</p>
        </div>
        <div className="header-actions">
          <span className="session-tag">Session: {shortSessionId(sessionId)}</span>
          {activeAgentName && (
            <span className="session-tag">Agent: {activeAgentName}</span>
          )}
          {activeToolName && (
            <span className="session-tag tool-tag">Tool: {activeToolName}</span>
          )}
          {isStreaming && (
            <button type="button" className="btn-stop" onClick={stopGeneration}>
              停止
            </button>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setSettingsOpen(true)}
            disabled={isStreaming}
          >
            设置
          </button>
          <button type="button" className="btn-secondary" onClick={() => setHelpOpen(true)}>
            帮助
          </button>
          <button type="button" className="btn-secondary" onClick={clearSession} disabled={isStreaming}>
            清空会话
          </button>
        </div>
      </header>

      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />

      <AgentSettingsSidebar
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        disabled={isStreaming}
        chatMode={chatMode}
        onChatModeChange={handleModeChange}
        showReasoning={showReasoning}
        onShowReasoningChange={handleShowReasoningChange}
        useServerHistory={useServerHistory}
        onUseServerHistoryChange={handleUseServerHistoryChange}
        maxHistoryMessages={maxHistoryMessages}
        onMaxHistoryChange={handleMaxHistoryChange}
        enableHistorySummary={enableHistorySummary}
        onEnableSummaryChange={handleEnableSummaryChange}
        useServerMcp={useServerMcp}
        onUseServerMcpChange={handleUseServerMcpChange}
        enableMcp={enableMcp}
        onEnableMcpChange={handleEnableMcpChange}
        mcpStatus={mcpStatus}
        mcpLoading={mcpLoading}
        mcpError={mcpError}
        onRefreshMcp={refreshMcp}
      />

      {backendOffline && (
        <div className="history-error backend-offline">
          <span>{historyError ?? "后端未连接"}</span>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleRetryBackend}
            disabled={retryingBackend}
          >
            {retryingBackend ? "连接中…" : "重试连接"}
          </button>
        </div>
      )}

      {historyError && !backendOffline && (
        <div className="history-error">历史加载失败：{historyError}</div>
      )}

      <main className="chat-main" ref={listRef}>
        {isLoadingHistory && messages.length === 0 && (
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
        <ErrorBoundary>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} showReasoning={showReasoning} />
          ))}
        </ErrorBoundary>
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
