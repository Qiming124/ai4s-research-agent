import { useState } from "react";
import type { ChatMode, AgentChoice, CotMode, ReasoningEffort } from "../utils/preferences";
import type { McpStatus } from "../hooks/useMcpStatus";
import {
  AGENT_GUIDE,
  AGENT_LABEL_ZH,
  formatAgentOptionLabel,
} from "../utils/agentMcpGuide";
import {
  AGENT_HELP_BLOCKS,
  AGENT_HELP_TITLE,
  MCP_HELP_BLOCKS,
  MCP_HELP_TITLE,
} from "../utils/contextHelpContent";
import { ContextHelpDrawer, ContextHelpTrigger } from "./ContextHelpDrawer";

interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
  disabled?: boolean;
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

const FALLBACK_AGENTS: { name: string; description: string }[] = [
  { name: "general", description: AGENT_LABEL_ZH.general },
  { name: "theory", description: AGENT_LABEL_ZH.theory },
  { name: "experiment", description: AGENT_LABEL_ZH.experiment },
  { name: "literature", description: AGENT_LABEL_ZH.literature },
  { name: "review", description: AGENT_LABEL_ZH.review },
  { name: "counterexample", description: AGENT_LABEL_ZH.counterexample },
];

export function SettingsDrawer({
  open,
  onClose,
  disabled,
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
  const [agentHelpOpen, setAgentHelpOpen] = useState(false);
  const [mcpHelpOpen, setMcpHelpOpen] = useState(false);

  if (!open) return null;

  const serverEnabled = mcpStatus?.server_enabled ?? false;
  const mcpToggleDisabled = disabled || useServerMcp || !serverEnabled;
  const agentOptions = serverAgents.length > 0 ? serverAgents : FALLBACK_AGENTS;
  const selectedZh =
    agentChoice === "auto"
      ? AGENT_LABEL_ZH.auto
      : AGENT_LABEL_ZH[agentChoice] ||
        agentOptions.find((a) => a.name === agentChoice)?.description ||
        "";

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
            <p className="settings-hint">Chat 通用对话；Math 更适合大量公式与推导。</p>
          </section>

          <section className="settings-section">
            <div className="settings-section-head">
              <h3>Agent 路由</h3>
              <ContextHelpTrigger onClick={() => setAgentHelpOpen(true)} />
            </div>
            <select
              className="agent-select"
              value={agentChoice}
              disabled={disabled}
              onChange={(e) => onAgentChoiceChange(e.target.value as AgentChoice)}
              aria-label="选择 Agent 或自动路由"
            >
              <option value="auto">{formatAgentOptionLabel("auto")}</option>
              {agentOptions.map((a) => (
                <option key={a.name} value={a.name}>
                  {formatAgentOptionLabel(a.name, a.description)}
                </option>
              ))}
            </select>
            {selectedZh && (
              <p className="settings-hint settings-agent-current">
                当前：{agentChoice === "auto" ? "自动路由" : agentChoice}
                {selectedZh ? `（${selectedZh}）` : ""}
                {" · "}
                {AGENT_GUIDE.find((g) => g.id === agentChoice)?.blurb ||
                  (agentChoice === "auto" ? "按问题自动分派合适角色。" : "")}
              </p>
            )}
          </section>

          <section className="settings-section">
            <h3>显示与推理</h3>
            <label className="pref-toggle">
              <input
                type="checkbox"
                checked={showReasoning}
                onChange={(e) => onShowReasoningChange(e.target.checked)}
                disabled={disabled}
              />
              显示思考过程
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
                <option value="high">high（较快）</option>
                <option value="max">max（更深）</option>
              </select>
            </label>
            {!useServerReasoning && (
              <p className="settings-hint">服务端默认：{serverReasoningEffort}</p>
            )}
            <label className="settings-field">
              思维链
              <select
                className="agent-select"
                value={cotMode}
                disabled={disabled}
                onChange={(e) => onCotModeChange(e.target.value as CotMode)}
              >
                <option value="off">关闭</option>
                <option value="standard">标准</option>
                <option value="strict">严格</option>
              </select>
            </label>
          </section>

          <section className="settings-section">
            <h3>上下文长度</h3>
            <label className="pref-toggle">
              <input
                type="checkbox"
                checked={useServerHistory}
                onChange={(e) => onUseServerHistoryChange(e.target.checked)}
                disabled={disabled}
              />
              使用服务端默认
            </label>
            <label className="settings-field">
              发给助手的最近消息条数（0=不限制）
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
              对更早消息做摘要（多耗一点额度）
            </label>
          </section>

          <section className="settings-section">
            <div className="settings-section-head">
              <h3>MCP 工具</h3>
              <div className="panel-header-actions">
                <ContextHelpTrigger onClick={() => setMcpHelpOpen(true)} />
                {onReloadMcp && (
                  <button
                    type="button"
                    className="btn-link"
                    onClick={() => void onReloadMcp()}
                    disabled={mcpLoading}
                  >
                    热重载
                  </button>
                )}
                <button type="button" className="btn-link" onClick={onRefreshMcp} disabled={mcpLoading}>
                  {mcpLoading ? "…" : "刷新"}
                </button>
              </div>
            </div>
            {mcpStatus?.servers && mcpStatus.servers.length > 0 && (
              <ul className="mcp-server-list mcp-server-list--status">
                {mcpStatus.servers.map((s) => (
                  <li key={s.name}>
                    {s.name}: {s.connected ? "已连接" : "未连接"} ({s.tools?.length ?? 0} 工具)
                  </li>
                ))}
              </ul>
            )}
            <label className="pref-toggle">
              <input
                type="checkbox"
                checked={useServerMcp}
                onChange={(e) => onUseServerMcpChange(e.target.checked)}
                disabled={disabled}
              />
              跟随服务端默认
            </label>
            <label className="pref-toggle">
              <input
                type="checkbox"
                checked={enableMcp}
                onChange={(e) => onEnableMcpChange(e.target.checked)}
                disabled={mcpToggleDisabled}
              />
              启用工具调用
            </label>
            {mcpError && <p className="settings-error">{mcpError}</p>}
          </section>
        </div>

        <ContextHelpDrawer
          open={agentHelpOpen}
          title={AGENT_HELP_TITLE}
          blocks={AGENT_HELP_BLOCKS}
          onClose={() => setAgentHelpOpen(false)}
        />
        <ContextHelpDrawer
          open={mcpHelpOpen}
          title={MCP_HELP_TITLE}
          blocks={MCP_HELP_BLOCKS}
          onClose={() => setMcpHelpOpen(false)}
        />
      </div>
    </div>
  );
}
