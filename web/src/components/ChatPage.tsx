import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useChatStream } from "../hooks/useChatStream";
import { useDocuments } from "../hooks/useDocuments";
import { useMcpStatus } from "../hooks/useMcpStatus";
import { useTokenStats } from "../hooks/useTokenStats";
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
import {
  createNewSession,
  getSessionList,
  removeSessionFromList,
  type SessionMeta,
} from "../utils/session";
import { AgentSettingsSidebar } from "./AgentSettingsSidebar";
import { ErrorBoundary } from "./ErrorBoundary";
import { HelpPanel } from "./HelpPanel";
import { MessageBubble } from "./MessageBubble";
import { SessionListSidebar } from "./SessionListSidebar";
import { TopStatusBar } from "./TopStatusBar";

export function ChatPage() {
  const [chatMode, setChatModeState] = useState<ChatMode>(getChatMode);
  const [showReasoning, setShowReasoningState] = useState(getShowReasoning);
  const [useServerHistory, setUseServerHistoryState] = useState(getUseServerHistoryDefault);
  const [maxHistoryMessages, setMaxHistoryMessagesState] = useState(getMaxHistoryMessages);
  const [enableHistorySummary, setEnableHistorySummaryState] = useState(getEnableHistorySummary);
  const [useServerMcp, setUseServerMcpState] = useState(getUseServerMcpDefault);
  const [enableMcp, setEnableMcpState] = useState(getEnableMcp);
  const [sessions, setSessions] = useState<SessionMeta[]>(getSessionList);

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
    sendMessage,
    stopGeneration,
    clearSession,
    reloadHistory,
    switchSession,
    createSession,
  } = useChatStream(chatMode, historyPref, mcpPref);

  const { stats: tokenStats, loading: tokenLoading, refresh: refreshTokens } = useTokenStats(
    sessionId,
    !backendOffline,
  );

  const {
    documents,
    loading: documentsLoading,
    uploading: documentsUploading,
    error: documentsError,
    refresh: refreshDocuments,
    uploadDocument,
    deleteDocument,
  } = useDocuments(!backendOffline);

  const [input, setInput] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [retryingBackend, setRetryingBackend] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const refreshSessions = useCallback(() => {
    setSessions(getSessionList());
  }, []);

  useEffect(() => {
    refreshSessions();
  }, [sessionId, messages, refreshSessions]);

  useEffect(() => {
    refreshMcp();
    refreshDocuments();
  }, [refreshMcp, refreshDocuments]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput("");
    refreshTokens();
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
        await refreshDocuments();
        await refreshTokens();
      }
    } finally {
      setRetryingBackend(false);
    }
  };

  const handleNewSession = async () => {
    const newId = createNewSession();
    await createSession(newId);
    refreshSessions();
  };

  const handleSelectSession = async (id: string) => {
    await switchSession(id);
    refreshSessions();
    refreshTokens();
  };

  const handleRemoveSession = async (id: string) => {
    if (isStreaming) return;
    await fetch(`/v1/sessions/${id}`, { method: "DELETE" });
    removeSessionFromList(id);
    const remaining = getSessionList();
    if (remaining.length === 0) {
      const newId = createNewSession();
      await createSession(newId);
    } else if (id === sessionId) {
      await switchSession(remaining[0].id);
    }
    refreshSessions();
  };

  return (
    <div className="chat-app">
      <header className="chat-header">
        <div className="chat-header-brand">
          <h1>AI4S 科研助手</h1>
          <p className="subtitle">多 Agent · MCP · RAG</p>
        </div>
        <TopStatusBar
          sessionId={sessionId}
          backendOffline={backendOffline}
          activeAgentName={activeAgentName}
          isStreaming={isStreaming}
          tokenStats={tokenStats}
          tokenLoading={tokenLoading}
          onStop={stopGeneration}
          onRetryBackend={handleRetryBackend}
          retryingBackend={retryingBackend}
        />
        <div className="header-actions">
          <button type="button" className="btn-secondary" onClick={() => setHelpOpen(true)}>
            帮助
          </button>
          <button type="button" className="btn-secondary" onClick={clearSession} disabled={isStreaming}>
            清空会话
          </button>
        </div>
      </header>

      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />

      {historyError && !backendOffline && (
        <div className="history-error">历史加载失败：{historyError}</div>
      )}

      <div className="chat-layout">
        <ErrorBoundary>
          <SessionListSidebar
            sessions={sessions}
            currentSessionId={sessionId}
            disabled={isStreaming}
            onSelect={handleSelectSession}
            onNewSession={handleNewSession}
            onRemove={handleRemoveSession}
          />
        </ErrorBoundary>

        <div className="chat-center">
          <main className="chat-main" ref={listRef}>
            {isLoadingHistory && messages.length === 0 && (
              <div className="history-loading">加载历史…</div>
            )}
            {!isLoadingHistory && messages.length === 0 && (
              <div className="empty-hint">
                <p>输入科研或数学问题开始对话。</p>
                <p className="hint-examples">
                  示例：什么是损失函数的局部极小值？ / 帮我检索 transformer 相关文献
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
              disabled={isStreaming || backendOffline}
            />
            <button
              type="button"
              className="btn-primary"
              onClick={handleSend}
              disabled={isStreaming || backendOffline || !input.trim()}
            >
              {isStreaming ? "生成中…" : "发送"}
            </button>
          </footer>
        </div>

        <ErrorBoundary>
          <AgentSettingsSidebar
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
            documents={documents}
            documentsLoading={documentsLoading}
            documentsUploading={documentsUploading}
            documentsError={documentsError}
            onRefreshDocuments={refreshDocuments}
            onUploadDocument={uploadDocument}
            onDeleteDocument={deleteDocument}
          />
        </ErrorBoundary>
      </div>
    </div>
  );
}
