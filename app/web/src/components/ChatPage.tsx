import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useChatStream } from "../hooks/useChatStream";
import { useDocuments } from "../hooks/useDocuments";
import { useMcpStatus } from "../hooks/useMcpStatus";
import { useTokenStats } from "../hooks/useTokenStats";
import { waitForBackend } from "../utils/backend";
import {
  getChatMode,
  getAgentChoice,
  getEnableHistorySummary,
  getEnableMcp,
  getMaxHistoryMessages,
  getShowReasoning,
  getUseServerHistoryDefault,
  getUseServerMcpDefault,
  setChatMode,
  setAgentChoice,
  setEnableHistorySummary,
  setEnableMcp,
  setMaxHistoryMessages,
  setShowReasoning,
  setUseServerHistoryDefault,
  setUseServerMcpDefault,
  type ChatMode,
  type AgentChoice,
} from "../utils/preferences";
import { useRagRefs } from "../hooks/useRagRefs";
import {
  createNewSession,
  fetchServerSessions,
  getSessionList,
  readSessionList,
  syncSessionListWithServer,
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
  const [agentChoice, setAgentChoiceState] = useState<AgentChoice>(getAgentChoice);
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

  const agentPref = { agent: agentChoice };

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
  } = useChatStream(chatMode, historyPref, mcpPref, agentPref);

  const sessionIdRef = useRef(sessionId);

  const {
    refs: ragRefs,
    loading: ragRefsLoading,
    error: ragRefsError,
    refresh: refreshRagRefs,
  } = useRagRefs(sessionId, !backendOffline);

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

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const refreshSessions = useCallback(async (currentId?: string) => {
    const cid = currentId ?? sessionIdRef.current;
    try {
      const server = await fetchServerSessions();
      setSessions(syncSessionListWithServer(server, cid));
    } catch {
      setSessions(getSessionList());
    }
  }, []);

  // 仅随 session 变化刷新列表，不依赖 messages（避免 SSE 流式时连锁重渲染）
  useEffect(() => {
    refreshSessions(sessionId);
  }, [sessionId, refreshSessions]);

  useEffect(() => {
    if (!isStreaming) {
      refreshRagRefs();
    }
  }, [isStreaming, refreshRagRefs]);

  useEffect(() => {
    refreshMcp();
    refreshDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const text = input;
    setInput("");
    await sendMessage(text);
    refreshTokens();
    await refreshSessions();
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

  const handleAgentChoiceChange = (value: AgentChoice) => {
    setAgentChoiceState(value);
    setAgentChoice(value);
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
    await refreshSessions(newId);
  };

  const handleSelectSession = async (id: string) => {
    await switchSession(id);
    await refreshSessions(id);
    refreshTokens();
  };

  const handleClearSession = async () => {
    await clearSession();
    await refreshSessions();
  };

  const handleRemoveSession = async (id: string) => {
    if (isStreaming) return;
    await fetch(`/v1/sessions/${id}?purge=true`, { method: "DELETE" });
    removeSessionFromList(id);

    if (id === sessionId) {
      const remaining = readSessionList();
      if (remaining.length === 0) {
        const newId = createNewSession();
        await createSession(newId);
        await refreshSessions(newId);
      } else {
        const nextId = remaining[0].id;
        await switchSession(nextId);
        await refreshSessions(nextId);
      }
    } else {
      await refreshSessions();
    }
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
          <button type="button" className="btn-secondary" onClick={handleClearSession} disabled={isStreaming}>
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
            agentChoice={agentChoice}
            onAgentChoiceChange={handleAgentChoiceChange}
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
            ragRefs={ragRefs}
            ragRefsLoading={ragRefsLoading}
            ragRefsError={ragRefsError}
            onRefreshRagRefs={refreshRagRefs}
          />
        </ErrorBoundary>
      </div>
    </div>
  );
}
