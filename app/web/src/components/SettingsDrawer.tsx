import type { ChatMode, AgentChoice, CotMode, ReasoningEffort } from "../utils/preferences";
import type { UiEdition } from "../utils/uiEdition";
import { UI_EDITION_OPTIONS } from "../utils/uiEdition";
import type { McpStatus } from "../hooks/useMcpStatus";

interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
  disabled?: boolean;
  uiEdition: UiEdition;
  onUiEditionChange: (edition: UiEdition) => void;
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
  onReloadMcp?: () => Promise<void>;
  serverAgents?: { name: string; description: string }[];
}

export function SettingsDrawer({
  open,
  onClose,
  disabled,
  uiEdition,
  onUiEditionChange,
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
  onReloadMcp,
  serverAgents = [],
}: SettingsDrawerProps) {
  if (!open) return null;

  const serverEnabled = mcpStatus?.server_enabled ?? false;
  const mcpToggleDisabled = disabled || useServerMcp || !serverEnabled;
  const editionHint =
    UI_EDITION_OPTIONS.find((o) => o.id === uiEdition)?.hint ?? "";

  return (
    <div className="settings-overlay" role="dialog" aria-modal="true" aria-label="高级设置">
      <button type="button" className="settings-overlay-backdrop" onClick={onClose} aria-label="关闭设置" />
      <div className="settings-drawer-panel">
        <header className="settings-drawer-head">
          <h2>高级设置</h2>
          <button type="button" className="btn-small" onClick={onClose}>
            关闭
          </button>
        </header>
        <div className="settings-drawer-body">
      <section className="settings-section">
        <h3>界面版本</h3>
        <div className="mode-toggle settings-mode-toggle" role="group" aria-label="界面版本">
          {UI_EDITION_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={uiEdition === opt.id ? "mode-btn active" : "mode-btn"}
              onClick={() => onUiEditionChange(opt.id)}
              disabled={disabled}
              title={opt.hint}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <p className="settings-hint">{editionHint}。仅影响界面入口，不限制 API。</p>
      </section>
      <section className="settings-section">
        <h3>对话模式</h3>
        <div className="mode-toggle settings-mode-toggle" role="group">
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
        <select
          className="agent-select"
          value={agentChoice}
          disabled={disabled}
          onChange={(e) => onAgentChoiceChange(e.target.value as AgentChoice)}
        >
          <option value="auto">自动路由</option>
          {serverAgents.length > 0
            ? serverAgents.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name}
                </option>
              ))
            : (
              <>
                <option value="general">General</option>
                <option value="theory">Theory</option>
                <option value="experiment">Experiment</option>
                <option value="literature">Literature</option>
                <option value="review">Review</option>
                <option value="counterexample">Counterexample</option>
              </>
            )}
        </select>
      </section>
      <section className="settings-section">
        <h3>显示与推理</h3>
        <label className="pref-toggle">
          <input type="checkbox" checked={showReasoning} onChange={(e) => onShowReasoningChange(e.target.checked)} disabled={disabled} />
          显示思考过程
        </label>
        <label className="pref-toggle">
          <input type="checkbox" checked={useServerReasoning} onChange={(e) => onUseServerReasoningChange(e.target.checked)} disabled={disabled} />
          推理策略：服务端默认
        </label>
        <label className="pref-toggle">
          <input
            type="checkbox"
            checked={enableThinking}
            onChange={(e) => onEnableThinkingChange(e.target.checked)}
            disabled={disabled || useServerReasoning}
          />
          启用深度思考
        </label>
        <label className="settings-field">
          推理强度
          <select
            className="agent-select"
            value={reasoningEffort}
            disabled={disabled || useServerReasoning}
            onChange={(e) => onReasoningEffortChange(e.target.value as ReasoningEffort)}
          >
            <option value="high">high</option>
            <option value="max">max</option>
          </select>
        </label>
        {!useServerReasoning && (
          <p className="settings-hint">服务端默认：{serverReasoningEffort}</p>
        )}
        <label className="settings-field">
          思维链
          <select className="agent-select" value={cotMode} disabled={disabled} onChange={(e) => onCotModeChange(e.target.value as CotMode)}>
            <option value="off">关闭</option>
            <option value="standard">标准</option>
            <option value="strict">严格</option>
          </select>
        </label>
      </section>
      <section className="settings-section">
        <h3>上下文 L1</h3>
        <label className="pref-toggle">
          <input type="checkbox" checked={useServerHistory} onChange={(e) => onUseServerHistoryChange(e.target.checked)} disabled={disabled} />
          历史策略：服务端默认
        </label>
        <label className="settings-field">
          保留条数
          <input
            type="number"
            className="history-num-input"
            min={0}
            value={maxHistoryMessages}
            disabled={disabled || useServerHistory}
            onChange={(e) => onMaxHistoryChange(Number(e.target.value))}
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
          <h3>MCP</h3>
          <div className="panel-header-actions">
            {onReloadMcp && (
              <button type="button" className="btn-link" onClick={() => void onReloadMcp()} disabled={mcpLoading}>
                热重载
              </button>
            )}
            <button type="button" className="btn-link" onClick={onRefreshMcp} disabled={mcpLoading}>
              {mcpLoading ? "…" : "刷新"}
            </button>
          </div>
        </div>
        {mcpStatus?.servers && mcpStatus.servers.length > 0 && (
          <ul className="mcp-server-list">
            {mcpStatus.servers.map((s) => (
              <li key={s.name}>
                {s.name}: {s.connected ? "已连接" : "未连接"} ({s.tools?.length ?? 0} 工具)
              </li>
            ))}
          </ul>
        )}
        <label className="pref-toggle">
          <input type="checkbox" checked={useServerMcp} onChange={(e) => onUseServerMcpChange(e.target.checked)} disabled={disabled} />
          MCP：服务端默认
        </label>
        <label className="pref-toggle">
          <input type="checkbox" checked={enableMcp} onChange={(e) => onEnableMcpChange(e.target.checked)} disabled={mcpToggleDisabled} />
          启用 MCP
        </label>
        {mcpError && <p className="settings-error">{mcpError}</p>}
      </section>
        </div>
      </div>
    </div>
  );
}
