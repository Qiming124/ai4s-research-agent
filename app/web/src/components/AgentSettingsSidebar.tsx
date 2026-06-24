import type { ChatMode, AgentChoice } from "../utils/preferences";
import type { McpStatus } from "../hooks/useMcpStatus";
import type { DocumentInfo } from "../hooks/useDocuments";
import { DocumentPanel } from "./DocumentPanel";
import { RagRefsPanel } from "./RagRefsPanel";
import type { RagRef } from "../hooks/useRagRefs";

interface AgentSettingsSidebarProps {
  chatMode: ChatMode;
  onChatModeChange: (mode: ChatMode) => void;
  agentChoice: AgentChoice;
  onAgentChoiceChange: (value: AgentChoice) => void;
  showReasoning: boolean;
  onShowReasoningChange: (value: boolean) => void;
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
            </select>
          </label>
          <p className="settings-hint">
            需服务端 ORCHESTRATION_BACKEND=langgraph 或 multi；自动路由时按意图分配 Agent。
          </p>
        </section>

        <section className="settings-section">
          <h3>显示</h3>
          <label className="pref-toggle">
            <input
              type="checkbox"
              checked={showReasoning}
              onChange={(e) => onShowReasoningChange(e.target.checked)}
              disabled={disabled}
            />
            显示思考过程
          </label>
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
