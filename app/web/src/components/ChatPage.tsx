import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useChatStream } from "../hooks/useChatStream";
import { useDocuments } from "../hooks/useDocuments";
import { useMcpStatus } from "../hooks/useMcpStatus";
import { useTokenStats } from "../hooks/useTokenStats";
import { useAgents } from "../hooks/useAgents";
import { useObservability } from "../hooks/useObservability";
import { useProjectSessions } from "../hooks/useProjectSessions";
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
  getEditionFeatures,
  clampWorkbenchTab,
  type ChatMode,
  type AgentChoice,
  type CotMode,
  type ReasoningEffort,
} from "../utils/preferences";
import { useRagRefs } from "../hooks/useRagRefs";
import { useExperimentLogs } from "../hooks/useExperimentLogs";
import { useLayoutPrefs } from "../hooks/useLayoutPrefs";
import { SIDEBAR_EDGE_WIDTH } from "../utils/layoutPrefs";
import { SidebarEdgeToggle } from "./SidebarEdgeToggle";
import { useStructuredMemory } from "../hooks/useStructuredMemory";
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
  updateSessionMeta,
  type SessionMeta,
} from "../utils/session";
import { ErrorBoundary } from "./ErrorBoundary";
import { HelpPanel } from "./HelpPanel";
import { MessageBubble } from "./MessageBubble";
import { ChatComposer } from "./ChatComposer";
import { OnboardingWizard, shouldShowOnboarding } from "./OnboardingWizard";
import { LeftSidebar } from "./LeftSidebar";
import { ResearchWorkbench } from "./ResearchWorkbench";
import { SettingsDrawer } from "./SettingsDrawer";
import { ResizeHandle } from "./ResizeHandle";
import { TheoremDetailDrawer } from "./TheoremDetailDrawer";
import { TheoremImportModal } from "./TheoremImportModal";
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
  const editionFeatures = getEditionFeatures("research");
  const [workbenchTab, setWorkbenchTab] = useState<WorkbenchTab>(() => {
    const clamped = clampWorkbenchTab("research", "literature");
    return clamped ?? "literature";
  });
  const [linkStatus, setLinkStatus] = useState<string | null>(null);
  const [projectMembers, setProjectMembers] = useState<{ user_id: string; role: string }[]>([]);

  const {
    projects,
    currentProject,
    currentProjectId,
    selectProject,
    createProject,
    updateProject,
    deleteProject,
    error: projectsError,
    refresh: refreshProjects,
  } = useProjects(true);

  const pipelineCallbacks = useMemo(
    () => ({
      onPipelineStage: (stage: string) => {
        const tab = pipelineStageToTab(stage);
        if (!tab) return;
        const clamped = clampWorkbenchTab("research", tab);
        if (clamped) setWorkbenchTab(clamped);
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
    currentProjectId,
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
  } = useDocuments(sessionId, !backendOffline, currentProjectId);

  const {
    entries: structuredEntries,
    loading: structuredLoading,
    error: structuredError,
    refresh: refreshStructured,
    createEntry: createStructuredEntry,
    updateEntry: updateStructuredEntry,
    deleteEntry: deleteStructuredEntry,
    previewMarkdown,
    previewFile,
    confirmImport,
  } = useStructuredMemory(sessionId, !backendOffline);

  const [importMode, setImportMode] = useState<"markdown" | "pdf" | null>(null);

  const {
    runs: experimentRuns,
    loading: experimentLoading,
    error: experimentError,
    refresh: refreshExperiments,
  } = useExperimentLogs(!backendOffline);

  const { sessions: _projectSessions, linkSession, refresh: refreshProjectSessions } =
    useProjectSessions(currentProjectId, !backendOffline);

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

  const filteredSessions = useMemo(() => sessions, [sessions]);

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

  const [helpOpen, setHelpOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(shouldShowOnboarding);
  const [selectedTheorem, setSelectedTheorem] = useState<StructuredMemoryEntry | null>(null);
  const [retryingBackend, setRetryingBackend] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const {
    prefs: layoutPrefs,
    resizeLeft,
    resizeRight,
    reset: resetLayout,
    toggleLeftCollapsed,
    toggleRightCollapsed,
  } = useLayoutPrefs();

  const layoutStyle = {
    "--layout-left": layoutPrefs.leftCollapsed
      ? `${SIDEBAR_EDGE_WIDTH}px`
      : `${layoutPrefs.leftWidth}px`,
    "--layout-right": layoutPrefs.rightCollapsed
      ? `${SIDEBAR_EDGE_WIDTH}px`
      : `${layoutPrefs.rightWidth}px`,
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

  const handleMoveSession = useCallback(
    async (sid: string, projectId: string) => {
      const res = await fetch(
        `/v1/projects/${encodeURIComponent(projectId)}/sessions/${encodeURIComponent(sid)}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(`关联失败 HTTP ${res.status}`);
      updateSessionMeta(sid, { projectId });
      selectProject(projectId);
      await refreshProjectSessions();
      await refreshSessions();
    },
    [refreshProjectSessions, refreshSessions, selectProject],
  );

  const handleUpdateSessionTitle = useCallback((sid: string, title: string) => {
    updateSessionMeta(sid, { title });
    setSessions(getSessionList());
  }, []);

  // 仅随 session 变化刷新列表，不依赖 messages（避免 SSE 流式时连锁重渲染）
  useEffect(() => {
    refreshSessions(sessionId);
  }, [sessionId, refreshSessions]);

  useEffect(() => {
    if (!isStreaming) {
      refreshRagRefs();
      refreshStructured();
      refreshExperiments();
      refreshVerification();
      refreshTasks();
    }
  }, [
    isStreaming,
    refreshRagRefs,
    refreshStructured,
    refreshExperiments,
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
    refreshObservability();
  }, [currentProjectId, backendOffline, refreshTasks, refreshVerification, refreshObservability]);

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

  const handleSend = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    await sendMessage(trimmed);
    refreshTokens();
    await refreshSessions();
  }, [sendMessage, refreshTokens, refreshSessions]);

  const handleModeChange = (mode: ChatMode) => {
    setChatModeState(mode);
    setChatMode(mode);
  };

  const handleAgentChoiceChange = (value: AgentChoice) => {
    setAgentChoiceState(value);
    setAgentChoice(value);
  };

  const handleWorkbenchTabChange = (tab: WorkbenchTab) => {
    const clamped = clampWorkbenchTab("research", tab);
    if (clamped) setWorkbenchTab(clamped);
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

  const handleNewSession = async (projectId?: string) => {
    const pid = projectId || currentProjectId || "default";
    const newId = createNewSession(pid);
    updateSessionMeta(newId, { projectId: pid });
    await createSession(newId);
    selectProject(pid);
    const res = await fetch(
      `/v1/projects/${encodeURIComponent(pid)}/sessions/${encodeURIComponent(newId)}`,
      { method: "POST" },
    );
    if (res.ok) {
      setLinkStatus(`会话已关联课题「${currentProject.name || pid}」`);
      await refreshProjectSessions();
    }
    await refreshSessions(newId);
  };

  const handleSelectSession = async (id: string, projectId?: string) => {
    if (projectId) {
      selectProject(projectId);
      updateSessionMeta(id, { projectId });
    }
    await switchSession(id);
    await refreshSessions(id);
    refreshTokens();
  };

  const handleJupyterUpload = async (payload: {
    name: string;
    project_id: string;
    session_id?: string | null;
    summary: Record<string, unknown>;
    metrics: Record<string, unknown>;
  }) => {
    const res = await fetch("/v1/jupyter/upload-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `回传失败 (${res.status})`);
    }
    await refreshExperiments();
  };

  const handleExperimentFileUpload = async (
    file: File,
    meta: { name: string; project_id: string; session_id?: string | null },
  ) => {
    const body = new FormData();
    body.append("file", file);
    body.append("name", meta.name);
    body.append("project_id", meta.project_id || "default");
    if (meta.session_id) body.append("session_id", meta.session_id);
    const res = await fetch("/v1/jupyter/upload-file", {
      method: "POST",
      body,
    });
    if (!res.ok) {
      let detail = await res.text();
      try {
        const j = JSON.parse(detail) as { detail?: string };
        if (j.detail) detail = j.detail;
      } catch {
        /* keep text */
      }
      throw new Error(detail || `文件上传失败 (${res.status})`);
    }
    await refreshExperiments();
  };

  const handleClearSession = async () => {
    await clearSession();
    await refreshSessions();
  };

  const handleDeleteProject = async (projectId: string) => {
    const data = await deleteProject(projectId);
    const deleted = new Set(data.deleted_sessions ?? []);
    for (const sid of deleted) {
      removeSessionFromList(sid);
    }
    // 当前会话属于被删课题 → 切到默认课题并新建会话
    if (deleted.has(sessionId) || deleted.size > 0) {
      const remaining = readSessionList().filter((s) => !deleted.has(s.id));
      if (deleted.has(sessionId) || remaining.length === 0) {
        const newId = createNewSession("default");
        updateSessionMeta(newId, { projectId: "default" });
        await createSession(newId);
        await fetch(
          `/v1/projects/default/sessions/${encodeURIComponent(newId)}`,
          { method: "POST" },
        );
        await refreshSessions(newId);
      } else {
        await refreshSessions();
      }
    } else {
      await refreshSessions();
    }
    setLinkStatus(`已删除课题「${data.name || projectId}」`);
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
          chatMode={chatMode}
          onChatModeChange={handleModeChange}
          onStop={stopGeneration}
          onRetryBackend={handleRetryBackend}
          retryingBackend={retryingBackend}
        />
        <div className="header-actions">
          <a className="btn-secondary" href="#/api-lab" title="自研 API 测试实验室">
            API 测试
          </a>
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
            title="恢复默认栏宽并展开左右侧栏"
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
      />
      <TheoremDetailDrawer
        entry={selectedTheorem}
        onClose={() => setSelectedTheorem(null)}
        onUpdate={async (id, payload) => {
          const updated = await updateStructuredEntry(id, payload);
          setSelectedTheorem(updated);
          await refreshStructured();
          return updated;
        }}
        onDelete={async (id) => {
          await deleteStructuredEntry(id);
          setSelectedTheorem(null);
          await refreshStructured();
        }}
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
      {importMode && (
        <TheoremImportModal
          mode={importMode}
          sessionId={sessionId}
          onClose={() => setImportMode(null)}
          onPreviewMarkdown={previewMarkdown}
          onPreviewFile={previewFile}
          onConfirm={async (candidates, source, extraMeta) => {
            const result = await confirmImport(candidates, source, extraMeta);
            await refreshStructured();
            return result;
          }}
          onAlsoUploadRag={async (file) => {
            const ok = await uploadFile(file);
            if (!ok) throw new Error("文献库上传失败");
            await refreshDocuments();
            await refreshRagRefs();
          }}
        />
      )}

      {historyError && !backendOffline && (
        <div className="history-error">历史加载失败：{historyError}</div>
      )}

      <div
        className={[
          editionFeatures.showWorkbench
            ? "chat-layout"
            : "chat-layout chat-layout--no-workbench",
          layoutPrefs.leftCollapsed ? "chat-layout--left-collapsed" : "",
          editionFeatures.showWorkbench && layoutPrefs.rightCollapsed
            ? "chat-layout--right-collapsed"
            : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={layoutStyle}
      >
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
            onUpdateProject={async (projectId, patch) => {
              await updateProject(projectId, patch);
            }}
            onDeleteProject={handleDeleteProject}
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
            onMoveSession={handleMoveSession}
            onUpdateSessionTitle={handleUpdateSessionTitle}
            allowedTabs={editionFeatures.leftTabs}
            collapsed={layoutPrefs.leftCollapsed}
            onToggleCollapse={toggleLeftCollapsed}
          />
        </ErrorBoundary>

        {layoutPrefs.leftCollapsed ? (
          <div className="resize-col-left resize-slot--collapsed" aria-hidden="true" />
        ) : (
          <ResizeHandle
            direction="horizontal"
            onResize={resizeLeft}
            className="resize-col-left"
            title="拖拽调整左侧栏宽度"
          />
        )}

        <div className="chat-center">
          <main className="chat-main" ref={listRef}>
            {isLoadingHistory && messages.length === 0 && (
              <div className="history-loading">加载历史…</div>
            )}
            {!isLoadingHistory && messages.length === 0 && (
              <div className="empty-hint">
                <p>输入科研或数学问题开始对话。</p>
                <p className="hint-examples">
                  示例：帮我检索某科学问题的相关文献 / 把这篇方法形式化推导一下 / 示范：什么是损失函数局部极小？
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} showReasoning={showReasoning} />
            ))}
          </main>

          <ChatComposer
            chatMode={chatMode}
            agentChoice={agentChoice}
            disabled={backendOffline}
            sendDisabled={isStreaming}
            onSend={handleSend}
            onPolishPresetSelected={() => {
              if (editionFeatures.showWorkbench) setWorkbenchTab("output");
            }}
          />
        </div>

        {editionFeatures.showWorkbench && (
          <>
        {layoutPrefs.rightCollapsed ? (
          <div className="resize-col-right resize-slot--collapsed" aria-hidden="true" />
        ) : (
          <ResizeHandle
            direction="horizontal"
            onResize={resizeRight}
            className="resize-col-right"
            title="拖拽调整右侧栏宽度"
          />
        )}

        <ErrorBoundary>
          <div
            className={
              layoutPrefs.rightCollapsed
                ? "right-column right-column--collapsed"
                : "right-column"
            }
          >
            <SidebarEdgeToggle
              side="right"
              collapsed={layoutPrefs.rightCollapsed}
              onToggle={toggleRightCollapsed}
            />
            {!layoutPrefs.rightCollapsed && (
            <ResearchWorkbench
              sessionId={sessionId}
              projectId={currentProjectId}
              disabled={isStreaming}
              activeTab={workbenchTab}
              onTabChange={handleWorkbenchTabChange}
              allowedTabs={editionFeatures.workbenchTabs}
              structuredEntries={structuredEntries}
              structuredLoading={structuredLoading}
              structuredError={structuredError}
              onRefreshStructured={refreshStructured}
              onSelectTheorem={setSelectedTheorem}
              onCreateTheorem={async (payload) => {
                await createStructuredEntry(payload);
                await refreshStructured();
              }}
              onOpenMarkdownImport={() => setImportMode("markdown")}
              onOpenPdfImport={() => setImportMode("pdf")}
              experimentRuns={experimentRuns}
              experimentLoading={experimentLoading}
              experimentError={experimentError}
              onRefreshExperiments={refreshExperiments}
              onJupyterUpload={handleJupyterUpload}
              onExperimentFileUpload={handleExperimentFileUpload}
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
            )}
          </div>
        </ErrorBoundary>
          </>
        )}
      </div>
    </div>
  );
}
