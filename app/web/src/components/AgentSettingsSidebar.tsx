import type { ChatMode, AgentChoice, CotMode, ReasoningEffort } from "../utils/preferences";
import type { McpStatus } from "../hooks/useMcpStatus";
import type { DocumentInfo } from "../hooks/useDocuments";
import type { RagRef } from "../hooks/useRagRefs";
import { DocumentPanel } from "./DocumentPanel";
import { ExperimentLogPanel } from "./ExperimentLogPanel";
import { KnowledgeGraphPanel } from "./KnowledgeGraphPanel";
import { RagRefsPanel } from "./RagRefsPanel";
import { TheoremLibraryPanel } from "./TheoremLibraryPanel";
import { WorkspacePanel } from "./WorkspacePanel";
import type { ExperimentRun } from "../hooks/useExperimentLogs";
import type { MemoryEdge } from "../hooks/useMemoryGraph";
import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import type { WorkspaceFile } from "../hooks/useWorkspaceFiles";

interface AgentSettingsSidebarProps {
  chatMode: ChatMode;
  onChatModeChange: (mode: ChatMode) => void;
  agentChoice: AgentChoice;
  onAgentChoiceChange: (value: AgentChoice) => void;
  showReasoning: boolean;
  onShowReasoningChange: (value: boolean) => void;
  useServerReasoning: boolean;
  onUseServerReasoningChange: (value: boolean) => void;
  enableThinking: boolean;
  onEnableThinkingChange: (value: boolean) => void;
  reasoningEffort: ReasoningEffort;
  onReasoningEffortChange: (value: ReasoningEffort) => void;
  serverReasoningEffort: ReasoningEffort;
  cotMode: CotMode;
  onCotModeChange: (value: CotMode) => void;
  useServerHistory: boolean;
  onUseServerHistoryChange: (value: boolean) => void;
  maxHistoryMessages: number;
  onMaxHistoryChange: (value: number) => void;
  enableHistorySummary: boolean;
  onEnableSummaryChange: (value: boolean) => void;
  useServerMcp: boolean;
  onUseServerMcpChange: (value: boolean) => void;
  enableMcp: boolean;
  onEnableMcpChange: (value: boolean) => void;
  mcpStatus: McpStatus | null;
  mcpLoading: boolean;
  mcpError: string | null;
  onRefreshMcp: () => void;
  disabled?: boolean;
  documents: DocumentInfo[];
  documentsLoading: boolean;
  documentsUploading: boolean;
  documentsError: string | null;
  onRefreshDocuments: () => void;
  onUploadDocument: (content: string, title?: string) => Promise<boolean>;
  onDeleteDocument: (docId: string) => Promise<boolean>;
  onClearAllDocuments?: () => Promise<boolean>;
  ragRefs: RagRef[];
  ragRefsLoading: boolean;
  ragRefsError: string | null;
  onRefreshRagRefs: () => void;
  structuredEntries: StructuredMemoryEntry[];
  structuredLoading: boolean;
  structuredError: string | null;
  onRefreshStructured: () => void;
  graphNodes: StructuredMemoryEntry[];
  graphEdges: MemoryEdge[];
  graphLoading: boolean;
  graphError: string | null;
  onRefreshGraph: () => void;
  experimentRuns: ExperimentRun[];
  experimentLoading: boolean;
  experimentError: string | null;
  onRefreshExperiments: () => void;
  workspaceFiles: WorkspaceFile[];
  workspaceLoading: boolean;
  workspaceError: string | null;
  onRefreshWorkspace: () => void;
}

function serverStatusLabel(
  server: McpStatus["servers"][number],
  serverEnabled: boolean,
): string {
  if (!serverEnabled) return "服务端未启用";
  if (!server.enabled) return "配置已禁用";
  if (server.connected) return "已连接";
  return "未连接";
}

export function AgentSettingsSidebar({
  chatMode,
  onChatModeChange,
  agentChoice,
  onAgentChoiceChange,
  showReasoning,
  onShowReasoningChange,
  useServerReasoning,
  onUseServerReasoningChange,
  enableThinking,
  onEnableThinkingChange,
  reasoningEffort,
  onReasoningEffortChange,
  serverReasoningEffort,
  cotMode,
  onCotModeChange,
  useServerHistory,
  onUseServerHistoryChange,
  maxHistoryMessages,
  onMaxHistoryChange,
  enableHistorySummary,
  onEnableSummaryChange,
  useServerMcp,
  onUseServerMcpChange,
  enableMcp,
  onEnableMcpChange,
  mcpStatus,
  mcpLoading,
  mcpError,
  onRefreshMcp,
  disabled = false,
  documents,
  documentsLoading,
  documentsUploading,
  documentsError,
  onRefreshDocuments,
  onUploadDocument,
  onDeleteDocument,
  onClearAllDocuments,
  ragRefs,
  ragRefsLoading,
  ragRefsError,
  onRefreshRagRefs,
  structuredEntries,
  structuredLoading,
  structuredError,
  onRefreshStructured,
  graphNodes,
  graphEdges,
  graphLoading,
  graphError,
  onRefreshGraph,
  experimentRuns,
  experimentLoading,
  experimentError,
  onRefreshExperiments,
  workspaceFiles,
  workspaceLoading,
  workspaceError,
  onRefreshWorkspace,
}: AgentSettingsSidebarProps) {
  const serverEnabled = mcpStatus?.server_enabled ?? false;
  const mcpToggleDisabled = disabled || useServerMcp || !serverEnabled;

  return (
    <aside className="settings-panel" aria-label="Agent 设置">
      <header className="settings-header">
        <div>
          <h2>设置</h2>
          <p className="settings-subtitle">模式、上下文、MCP 与 RAG</p>
        </div>
      </header>

      <div className="settings-body">
        <section className="settings-section">
          <h3>对话模式</h3>
          <div className="mode-toggle settings-mode-toggle" role="group" aria-label="对话模式">
            <button
              type="button"
              className={chatMode === "chat" ? "mode-btn active" : "mode-btn"}
              onClick={() => onChatModeChange("chat")}
              disabled={disabled}
            >
              Chat
            </button>
            <button
              type="button"
              className={chatMode === "math" ? "mode-btn active" : "mode-btn"}
              onClick={() => onChatModeChange("math")}
              disabled={disabled}
            >
              Math
            </button>
          </div>
        </section>

        <section className="settings-section">
          <h3>Agent 路由</h3>
          <label className="settings-field">
            目标 Agent
            <select
              className="agent-select"
              value={agentChoice}
              disabled={disabled}
              onChange={(e) => onAgentChoiceChange(e.target.value as AgentChoice)}
            >
              <option value="auto">自动路由（Supervisor）</option>
              <option value="general">General — 通用</option>
              <option value="theory">Theory — 理论推导</option>
              <option value="experiment">Experiment — 实验分析</option>
              <option value="literature">Literature — 文献检索</option>
              <option value="review">Review — 审稿</option>
            </select>
          </label>
          <p className="settings-hint">
            需服务端 ORCHESTRATION_BACKEND=langgraph 或 multi；自动路由时按意图分配 Agent。
          </p>
        </section>

        <section className="settings-section">
          <h3>显示与思维链</h3>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={showReasoning}
              onChange={(e) => onShowReasoningChange(e.target.checked)}
              disabled={disabled}
            />
            显示思考过程（模型内部推理）
          </label>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={useServerReasoning}
              onChange={(e) => onUseServerReasoningChange(e.target.checked)}
              disabled={disabled}
            />
            推理策略：服务端默认
          </label>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={enableThinking}
              onChange={(e) => onEnableThinkingChange(e.target.checked)}
              disabled={disabled || useServerReasoning}
            />
            启用深度思考（DeepSeek thinking）
          </label>
          <label className="settings-field">
            推理强度
            <select
              className="agent-select"
              value={reasoningEffort}
              disabled={disabled || useServerReasoning}
              onChange={(e) => onReasoningEffortChange(e.target.value as ReasoningEffort)}
            >
              <option value="high">high — 较快</option>
              <option value="max">max — 更深</option>
            </select>
          </label>
          {!useServerReasoning && (
            <p className="settings-hint">
              服务端默认推理强度：{serverReasoningEffort}。max 消耗更多 token。
            </p>
          )}
          <label className="settings-field">
            思维链模式（回答结构）
            <select
              className="agent-select"
              value={cotMode}
              disabled={disabled}
              onChange={(e) => onCotModeChange(e.target.value as CotMode)}
            >
              <option value="off">关闭</option>
              <option value="standard">标准（问题分析 → 推理 → 结论）</option>
              <option value="strict">严格（强制 Markdown 三节）</option>
            </select>
          </label>
          <p className="settings-hint">
            Math 模式自动使用严格思维链。Theory Agent 使用专用五阶段推导。
          </p>
        </section>

        <section className="settings-section">
          <h3>上下文（L1 工作记忆）</h3>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={useServerHistory}
              onChange={(e) => onUseServerHistoryChange(e.target.checked)}
              disabled={disabled}
            />
            历史策略：服务端默认
          </label>
          <label className="pref-inline settings-field">
            保留条数
            <input
              type="number"
              className="history-num-input"
              min={0}
              value={maxHistoryMessages}
              disabled={disabled || useServerHistory}
              onChange={(e) => onMaxHistoryChange(Number(e.target.value))}
              title="0 表示不截断；大于 0 时只向 LLM 发送最近 N 条"
            />
          </label>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={enableHistorySummary}
              disabled={disabled || useServerHistory || maxHistoryMessages === 0}
              onChange={(e) => onEnableSummaryChange(e.target.checked)}
            />
            LLM 摘要旧消息
          </label>
        </section>

        <section className="settings-section">
          <div className="settings-section-head">
            <h3>MCP 工具</h3>
            <button
              type="button"
              className="btn-link"
              onClick={onRefreshMcp}
              disabled={mcpLoading}
            >
              {mcpLoading ? "刷新中…" : "刷新"}
            </button>
          </div>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={useServerMcp}
              onChange={(e) => onUseServerMcpChange(e.target.checked)}
              disabled={disabled}
            />
            MCP：服务端默认
          </label>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={enableMcp}
              onChange={(e) => onEnableMcpChange(e.target.checked)}
              disabled={mcpToggleDisabled}
            />
            启用 MCP 工具
          </label>
          {!serverEnabled && (
            <p className="settings-hint">
              服务端未启用 MCP。请在 .env 设置 ENABLE_MCP=true 并重启后端。
            </p>
          )}
          {mcpError && <p className="settings-error">加载失败：{mcpError}</p>}
          <div className="mcp-server-list">
            {(mcpStatus?.servers ?? []).map((server) => (
              <details key={server.name} className="mcp-server-item">
                <summary className="mcp-server-summary">
                  <span className="mcp-server-name">{server.name}</span>
                  <span className={`mcp-server-badge mcp-badge-${server.connected ? "ok" : "off"}`}>
                    {serverStatusLabel(server, serverEnabled)}
                  </span>
                </summary>
                {server.tools.length === 0 ? (
                  <p className="mcp-tool-empty">暂无工具信息</p>
                ) : (
                  <ul className="mcp-tool-list">
                    {server.tools.map((tool) => (
                      <li key={tool.qualified_name} className="mcp-tool-item">
                        <code className="mcp-tool-name">{tool.qualified_name}</code>
                        {tool.description && (
                          <span className="mcp-tool-desc">{tool.description}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </details>
            ))}
            {mcpStatus && mcpStatus.servers.length === 0 && !mcpLoading && (
              <p className="settings-hint">未配置 MCP Server</p>
            )}
          </div>
        </section>

        <section className="settings-section">
          <RagRefsPanel
            refs={ragRefs}
            loading={ragRefsLoading}
            error={ragRefsError}
            onRefresh={onRefreshRagRefs}
            disabled={disabled}
          />
        </section>

        <section className="settings-section">
          <TheoremLibraryPanel
            entries={structuredEntries}
            loading={structuredLoading}
            error={structuredError}
            onRefresh={onRefreshStructured}
          />
        </section>

        <section className="settings-section">
          <KnowledgeGraphPanel
            nodes={graphNodes}
            edges={graphEdges}
            loading={graphLoading}
            error={graphError}
            onRefresh={onRefreshGraph}
          />
        </section>

        <section className="settings-section">
          <ExperimentLogPanel
            runs={experimentRuns}
            loading={experimentLoading}
            error={experimentError}
            onRefresh={onRefreshExperiments}
          />
        </section>

        <section className="settings-section">
          <WorkspacePanel
            files={workspaceFiles}
            loading={workspaceLoading}
            error={workspaceError}
            onRefresh={onRefreshWorkspace}
          />
        </section>

        <section className="settings-section">
          <DocumentPanel
            documents={documents}
            loading={documentsLoading}
            uploading={documentsUploading}
            error={documentsError}
            disabled={disabled}
            onRefresh={onRefreshDocuments}
            onUpload={onUploadDocument}
            onDelete={onDeleteDocument}
            onClearAll={onClearAllDocuments}
          />
        </section>
      </div>
    </aside>
  );
}
