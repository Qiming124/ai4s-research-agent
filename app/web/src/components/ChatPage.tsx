import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { useChatStream } from "../hooks/useChatStream";
import { useDocuments } from "../hooks/useDocuments";
import { useMcpStatus } from "../hooks/useMcpStatus";
import { useTokenStats } from "../hooks/useTokenStats";
import { useAgents } from "../hooks/useAgents";
import { useAssumptionDag } from "../hooks/useAssumptionDag";
import { useBibliography } from "../hooks/useBibliography";
import { useObservability } from "../hooks/useObservability";
import { useProjectSessions } from "../hooks/useProjectSessions";
import { useTheoryAssets } from "../hooks/useTheoryAssets";
import { useVerificationRecords } from "../hooks/useVerificationRecords";
import { waitForBackend } from "../utils/backend";
import { pipelineStageToTab, type WorkbenchTab } from "../utils/workbenchTabs";
import {
  getChatMode,
  getAgentChoice,
  getCotMode,
  getEnableHistorySummary,
  getEnableMcp,
  getEnableThinking,
  getMaxHistoryMessages,
  getReasoningEffort,
  getShowReasoning,
  getUseServerHistoryDefault,
  getUseServerMcpDefault,
  getUseServerReasoningDefault,
  setChatMode,
  setAgentChoice,
  setCotMode,
  setEnableHistorySummary,
  setEnableMcp,
  setEnableThinking,
  setMaxHistoryMessages,
  setReasoningEffort,
  setShowReasoning,
  setUseServerHistoryDefault,
  setUseServerMcpDefault,
  setUseServerReasoningDefault,
  type ChatMode,
  type AgentChoice,
  type CotMode,
  type ReasoningEffort,
} from "../utils/preferences";
import { useRagRefs } from "../hooks/useRagRefs";
import { useExperimentLogs } from "../hooks/useExperimentLogs";
import { useLayoutPrefs } from "../hooks/useLayoutPrefs";
import { useMemoryGraph } from "../hooks/useMemoryGraph";
import { useStructuredMemory } from "../hooks/useStructuredMemory";
import { useWorkspaceFiles } from "../hooks/useWorkspaceFiles";
import { useProjects } from "../hooks/useProjects";
import { useVerification } from "../hooks/useVerification";
import { useProjectTasks } from "../hooks/useProjectTasks";
import {
  createNewSession,
  fetchServerSessions,
  getSessionList,
  readSessionList,
  syncSessionListWithServer,
  removeSessionFromList,
  type SessionMeta,
} from "../utils/session";
import { ErrorBoundary } from "./ErrorBoundary";
import { HelpPanel } from "./HelpPanel";
import { MessageBubble } from "./MessageBubble";
import { OnboardingWizard, shouldShowOnboarding } from "./OnboardingWizard";
import { LeftSidebar } from "./LeftSidebar";
import { ResearchWorkbench } from "./ResearchWorkbench";
import { SettingsDrawer } from "./SettingsDrawer";
import { ResizeHandle } from "./ResizeHandle";
import { TheoremDetailDrawer } from "./TheoremDetailDrawer";
import { TopStatusBar } from "./TopStatusBar";
import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";

export function ChatPage() {
  const [chatMode, setChatModeState] = useState<ChatMode>(getChatMode);
  const [agentChoice, setAgentChoiceState] = useState<AgentChoice>(getAgentChoice);
  const [showReasoning, setShowReasoningState] = useState(getShowReasoning);
  const [useServerReasoning, setUseServerReasoningState] = useState(getUseServerReasoningDefault);
  const [enableThinking, setEnableThinkingState] = useState(getEnableThinking);
  const [reasoningEffort, setReasoningEffortState] = useState<ReasoningEffort>(getReasoningEffort);
  const [cotMode, setCotModeState] = useState<CotMode>(getCotMode);
  const [serverReasoningEffort, setServerReasoningEffort] = useState<ReasoningEffort>("max");
  const [useServerHistory, setUseServerHistoryState] = useState(getUseServerHistoryDefault);
  const [maxHistoryMessages, setMaxHistoryMessagesState] = useState(getMaxHistoryMessages);
  const [enableHistorySummary, setEnableHistorySummaryState] = useState(getEnableHistorySummary);
  const [useServerMcp, setUseServerMcpState] = useState(getUseServerMcpDefault);
  const [enableMcp, setEnableMcpState] = useState(getEnableMcp);
  const [sessions, setSessions] = useState<SessionMeta[]>(getSessionList);
  const [workbenchTab, setWorkbenchTab] = useState<WorkbenchTab>("literature");
  const [linkStatus, setLinkStatus] = useState<string | null>(null);
  const [projectMembers, setProjectMembers] = useState<{ user_id: string; role: string }[]>([]);

  const pipelineCallbacks = useMemo(
    () => ({
      onPipelineStage: (stage: string) => {
        const tab = pipelineStageToTab(stage);
        if (tab) setWorkbenchTab(tab);
      },
    }),
    [],
  );

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

  const reasoningPref = {
    useServerDefault: useServerReasoning,
    enableThinking,
    reasoningEffort,
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
    switchSession,
    createSession,
  } = useChatStream(
    chatMode,
    historyPref,
    mcpPref,
    agentPref,
    reasoningPref,
    cotMode,
    pipelineCallbacks,
  );

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
    uploadFile,
    ingestArxiv,
    deleteDocument,
    clearAllDocuments,
  } = useDocuments(sessionId, !backendOffline);

  const {
    entries: structuredEntries,
    loading: structuredLoading,
    error: structuredError,
    refresh: refreshStructured,
  } = useStructuredMemory(sessionId, !backendOffline);

  const {
    nodes: graphNodes,
    edges: graphEdges,
    loading: graphLoading,
    error: graphError,
    refresh: refreshGraph,
  } = useMemoryGraph(sessionId, !backendOffline);

  const {
    runs: experimentRuns,
    loading: experimentLoading,
    error: experimentError,
    refresh: refreshExperiments,
  } = useExperimentLogs(!backendOffline);

  const {
    files: workspaceFiles,
    loading: workspaceLoading,
    error: workspaceError,
    refresh: refreshWorkspace,
  } = useWorkspaceFiles(!backendOffline);

  const {
    projects,
    currentProject,
    currentProjectId,
    selectProject,
    createProject,
    error: projectsError,
    refresh: refreshProjects,
  } = useProjects(!backendOffline);

  const { sessions: projectSessions, linkSession, refresh: refreshProjectSessions } =
    useProjectSessions(currentProjectId, !backendOffline);

  const {
    symbols: theorySymbols,
    assumptions: theoryAssumptions,
    matrix: theoryMatrix,
    loading: theoryAssetsLoading,
    error: theoryAssetsError,
    refresh: refreshTheoryAssets,
  } = useTheoryAssets(!backendOffline);

  const {
    nodes: dagNodes,
    edges: dagEdges,
    loading: dagLoading,
    error: dagError,
    refresh: refreshDag,
    fetchImpact: fetchDagImpact,
  } = useAssumptionDag(!backendOffline);

  const {
    entries: bibEntries,
    loading: bibLoading,
    error: bibError,
    refresh: refreshBib,
    exportBib,
  } = useBibliography(currentProjectId, !backendOffline);

  const {
    records: verificationRecords,
    loading: verificationRecordsLoading,
    refresh: refreshVerificationRecords,
    runVerification,
  } = useVerificationRecords(currentProjectId, sessionId, !backendOffline);

  const {
    summary: observabilitySummary,
    agentQuality,
    loading: observabilityLoading,
    error: observabilityError,
    refresh: refreshObservability,
  } = useObservability(currentProjectId, !backendOffline);

  const { agents: serverAgents } = useAgents(!backendOffline);

  const filteredSessions = useMemo(() => {
    const linked = new Set(projectSessions.map((s) => s.session_id));
    if (linked.size === 0) return sessions;
    return sessions.filter((s) => linked.has(s.id) || s.id === sessionId);
  }, [sessions, projectSessions, sessionId]);

  const {
    dashboard: verificationDashboard,
    loading: verificationLoading,
    error: verificationError,
    refresh: refreshVerification,
  } = useVerification(sessionId, currentProjectId, !backendOffline);

  const {
    tasks: projectTasks,
    loading: tasksLoading,
    error: tasksError,
    refresh: refreshTasks,
    updateStatus: updateTaskStatus,
    createTask,
  } = useProjectTasks(currentProjectId, !backendOffline);

  const [input, setInput] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(shouldShowOnboarding);
  const [selectedTheorem, setSelectedTheorem] = useState<StructuredMemoryEntry | null>(null);
  const [retryingBackend, setRetryingBackend] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const { prefs: layoutPrefs, resizeLeft, resizeRight, reset: resetLayout } = useLayoutPrefs();

  const layoutStyle = {
    "--layout-left": `${layoutPrefs.leftWidth}px`,
    "--layout-right": `${layoutPrefs.rightWidth}px`,
  } as CSSProperties;

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
      refreshStructured();
      refreshGraph();
      refreshExperiments();
      refreshWorkspace();
      refreshVerification();
      refreshTasks();
    }
  }, [
    isStreaming,
    refreshRagRefs,
    refreshStructured,
    refreshGraph,
    refreshExperiments,
    refreshWorkspace,
    refreshVerification,
    refreshTasks,
  ]);

  useEffect(() => {
    if (!sessionId || backendOffline) return;
    linkSession(sessionId).then((ok) => {
      setLinkStatus(ok ? `会话已关联课题「${currentProject.name || currentProjectId}」` : null);
      if (ok) refreshProjectSessions();
    });
  }, [sessionId, currentProjectId, backendOffline, linkSession, refreshProjectSessions, currentProject.name, currentProjectId]);

  useEffect(() => {
    if (!currentProjectId || backendOffline) return;
    fetch(`/v1/projects/${encodeURIComponent(currentProjectId)}/members`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setProjectMembers(Array.isArray(data) ? data : []))
      .catch(() => setProjectMembers([]));
    refreshTasks();
    refreshVerification();
    refreshBib();
    refreshObservability();
  }, [currentProjectId, backendOffline, refreshTasks, refreshVerification, refreshBib, refreshObservability]);

  useEffect(() => {
    refreshMcp();
    refreshDocuments();
    waitForBackend(3, 500).then(async (ok) => {
      if (!ok) return;
      try {
        const res = await fetch("/health");
        if (res.ok) {
          const data = (await res.json()) as { reasoning_effort?: string };
          if (data.reasoning_effort === "high" || data.reasoning_effort === "max") {
            setServerReasoningEffort(data.reasoning_effort);
          }
        }
      } catch {
        /* ignore */
      }
    });
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

  const handleUseServerReasoningChange = (checked: boolean) => {
    setUseServerReasoningState(checked);
    setUseServerReasoningDefault(checked);
  };

  const handleEnableThinkingChange = (checked: boolean) => {
    setEnableThinkingState(checked);
    setEnableThinking(checked);
  };

  const handleReasoningEffortChange = (value: ReasoningEffort) => {
    setReasoningEffortState(value);
    setReasoningEffort(value);
  };

  const handleCotModeChange = (value: CotMode) => {
    setCotModeState(value);
    setCotMode(value);
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
    await linkSession(newId);
    await refreshSessions(newId);
  };

  const handleRunExperiment = async () => {
    await fetch("/v1/experiments/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config_path: "quadratic_minimum.yaml" }),
    });
    await refreshExperiments();
  };

  const handleJupyterTemplate = async () => {
    const res = await fetch("/v1/jupyter/template");
    if (!res.ok) return;
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "notebook-template.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleJupyterUpload = async () => {
    await fetch("/v1/jupyter/upload-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "ui-upload", summary: { ok: true }, metrics: { loss: 0.1 } }),
    });
    await refreshExperiments();
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

  const handleRunResearch = async () => {
    const text = input.trim() ? `/research ${input.trim()}` : "/research 请对损失函数局部极小值进行完整研究";
    setInput("");
    setSettingsOpen(false);
    await sendMessage(text);
    refreshTokens();
    await refreshSessions();
  };

  const handleRemoveSession = async (id: string) => {
    if (isStreaming) return;
    if (!window.confirm("确定删除此会话？")) return;
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
          activeToolName={activeToolName}
          isStreaming={isStreaming}
          tokenStats={tokenStats}
          tokenLoading={tokenLoading}
          onStop={stopGeneration}
          onRetryBackend={handleRetryBackend}
          retryingBackend={retryingBackend}
        />
        <div className="header-actions">
          <button type="button" className="btn-secondary" onClick={() => setSettingsOpen(true)}>
            设置
          </button>
          <button type="button" className="btn-secondary" onClick={() => setHelpOpen(true)}>
            帮助
          </button>
          <button type="button" className="btn-secondary" onClick={handleClearSession} disabled={isStreaming}>
            清空会话
          </button>
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={resetLayout}
            title="恢复默认栏宽"
          >
            重置布局
          </button>
        </div>
      </header>

      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />
      {showOnboarding && <OnboardingWizard onComplete={() => setShowOnboarding(false)} />}
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        disabled={isStreaming}
        chatMode={chatMode}
        onChatModeChange={handleModeChange}
        agentChoice={agentChoice}
        onAgentChoiceChange={handleAgentChoiceChange}
        showReasoning={showReasoning}
        onShowReasoningChange={handleShowReasoningChange}
        useServerReasoning={useServerReasoning}
        onUseServerReasoningChange={handleUseServerReasoningChange}
        enableThinking={enableThinking}
        onEnableThinkingChange={handleEnableThinkingChange}
        reasoningEffort={reasoningEffort}
        onReasoningEffortChange={handleReasoningEffortChange}
        serverReasoningEffort={serverReasoningEffort}
        cotMode={cotMode}
        onCotModeChange={handleCotModeChange}
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
        onReloadMcp={async () => {
          await fetch("/v1/mcp/reload", { method: "POST" });
          await refreshMcp();
        }}
        serverAgents={serverAgents}
        onRunResearch={handleRunResearch}
      />
      <TheoremDetailDrawer
        entry={selectedTheorem}
        onClose={() => setSelectedTheorem(null)}
        onCreateTask={async (title, entryId) => {
          await fetch(`/v1/projects/${encodeURIComponent(currentProjectId)}/tasks`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              title,
              assignee_role: "theorist",
              related_entry_id: entryId,
            }),
          });
          await refreshTasks();
        }}
      />

      {historyError && !backendOffline && (
        <div className="history-error">历史加载失败：{historyError}</div>
      )}

      <div className="chat-layout" style={layoutStyle}>
        <ErrorBoundary>
          <LeftSidebar
            projects={projects.length ? projects : [currentProject]}
            currentProjectId={currentProjectId}
            currentProject={currentProject}
            onSelectProject={selectProject}
            onCreateProject={async (name, description) => {
              await createProject(name, description);
              await refreshProjects();
            }}
            projectsError={projectsError}
            linkStatus={linkStatus}
            projectMembers={projectMembers}
            tasks={projectTasks}
            tasksLoading={tasksLoading}
            tasksError={tasksError}
            onRefreshTasks={refreshTasks}
            onUpdateTaskStatus={updateTaskStatus}
            onCreateTask={createTask}
            sessions={filteredSessions}
            currentSessionId={sessionId}
            disabled={isStreaming}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onRemoveSession={handleRemoveSession}
          />
        </ErrorBoundary>

        <ResizeHandle
          direction="horizontal"
          onResize={resizeLeft}
          className="resize-col-left"
          title="拖拽调整左侧栏宽度"
        />

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
            <div className="mode-toggle footer-mode-toggle" role="group">
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
            <button
              type="button"
              className="btn-secondary btn-research"
              onClick={handleRunResearch}
              disabled={isStreaming || backendOffline}
              title="运行 literature→theory→experiment→review 流水线"
            >
              完整研究
            </button>
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

        <ResizeHandle
          direction="horizontal"
          onResize={resizeRight}
          className="resize-col-right"
          title="拖拽调整右侧栏宽度"
        />

        <ErrorBoundary>
          <div className="right-column">
            <ResearchWorkbench
              sessionId={sessionId}
              projectId={currentProjectId}
              disabled={isStreaming}
              activeTab={workbenchTab}
              onTabChange={setWorkbenchTab}
              structuredEntries={structuredEntries}
              structuredLoading={structuredLoading}
              structuredError={structuredError}
              onRefreshStructured={refreshStructured}
              onSelectTheorem={setSelectedTheorem}
              graphNodes={graphNodes}
              graphEdges={graphEdges}
              graphLoading={graphLoading}
              graphError={graphError}
              onRefreshGraph={refreshGraph}
              experimentRuns={experimentRuns}
              experimentLoading={experimentLoading}
              experimentError={experimentError}
              onRefreshExperiments={refreshExperiments}
              onRunExperiment={handleRunExperiment}
              onJupyterTemplate={handleJupyterTemplate}
              onJupyterUpload={handleJupyterUpload}
              workspaceFiles={workspaceFiles}
              workspaceLoading={workspaceLoading}
              workspaceError={workspaceError}
              onRefreshWorkspace={refreshWorkspace}
              theorySymbols={theorySymbols}
              theoryAssumptions={theoryAssumptions}
              theoryMatrix={theoryMatrix}
              theoryAssetsLoading={theoryAssetsLoading}
              theoryAssetsError={theoryAssetsError}
              onRefreshTheoryAssets={refreshTheoryAssets}
              dagNodes={dagNodes}
              dagEdges={dagEdges}
              dagLoading={dagLoading}
              dagError={dagError}
              onRefreshDag={refreshDag}
              onDagImpact={fetchDagImpact}
              bibEntries={bibEntries}
              bibLoading={bibLoading}
              bibError={bibError}
              onRefreshBib={refreshBib}
              onExportBib={exportBib}
              documents={documents}
              documentsLoading={documentsLoading}
              documentsUploading={documentsUploading}
              documentsError={documentsError}
              onRefreshDocuments={refreshDocuments}
              onUploadDocument={uploadDocument}
              onUploadFile={uploadFile}
              onIngestArxiv={ingestArxiv}
              onDeleteDocument={deleteDocument}
              onClearAllDocuments={clearAllDocuments}
              ragRefs={ragRefs}
              ragRefsLoading={ragRefsLoading}
              ragRefsError={ragRefsError}
              onRefreshRagRefs={refreshRagRefs}
              verificationDashboard={verificationDashboard}
              verificationLoading={verificationLoading}
              verificationError={verificationError}
              verificationRecords={verificationRecords}
              verificationRecordsLoading={verificationRecordsLoading}
              onRefreshVerification={refreshVerification}
              onRefreshVerificationRecords={refreshVerificationRecords}
              onRunVerification={runVerification}
              observabilitySummary={observabilitySummary}
              agentQuality={agentQuality}
              observabilityLoading={observabilityLoading}
              observabilityError={observabilityError}
              onRefreshObservability={refreshObservability}
            />
          </div>
        </ErrorBoundary>
      </div>
    </div>
  );
}
