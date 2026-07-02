const SHOW_REASONING_KEY = "ai4s_show_reasoning";
const ENABLE_THINKING_KEY = "ai4s_enable_thinking";
const REASONING_EFFORT_KEY = "ai4s_reasoning_effort";
const USE_SERVER_REASONING_KEY = "ai4s_use_server_reasoning";
const COT_MODE_KEY = "ai4s_cot_mode";
const CHAT_MODE_KEY = "ai4s_chat_mode";
const USE_SERVER_HISTORY_KEY = "ai4s_use_server_history";
const MAX_HISTORY_MESSAGES_KEY = "ai4s_max_history_messages";
const ENABLE_HISTORY_SUMMARY_KEY = "ai4s_enable_history_summary";
const USE_SERVER_MCP_KEY = "ai4s_use_server_mcp";
const ENABLE_MCP_KEY = "ai4s_enable_mcp";

export type ChatMode = "chat" | "math";

export type AgentChoice = "auto" | "general" | "theory" | "experiment" | "literature" | "review";

export type ReasoningEffort = "high" | "max";

export type CotMode = "off" | "standard" | "strict";

const AGENT_CHOICE_KEY = "ai4s_agent_choice";

export function getShowReasoning(): boolean {
  const raw = localStorage.getItem(SHOW_REASONING_KEY);
  if (raw === null) return true;
  return raw === "true";
}

export function setShowReasoning(value: boolean): void {
  localStorage.setItem(SHOW_REASONING_KEY, String(value));
}

export function getUseServerReasoningDefault(): boolean {
  const raw = localStorage.getItem(USE_SERVER_REASONING_KEY);
  if (raw === null) return true;
  return raw === "true";
}

export function setUseServerReasoningDefault(value: boolean): void {
  localStorage.setItem(USE_SERVER_REASONING_KEY, String(value));
}

export function getEnableThinking(): boolean {
  const raw = localStorage.getItem(ENABLE_THINKING_KEY);
  if (raw === null) return true;
  return raw === "true";
}

export function setEnableThinking(value: boolean): void {
  localStorage.setItem(ENABLE_THINKING_KEY, String(value));
}

export function getReasoningEffort(): ReasoningEffort {
  const raw = localStorage.getItem(REASONING_EFFORT_KEY);
  return raw === "high" ? "high" : "max";
}

export function setReasoningEffort(value: ReasoningEffort): void {
  localStorage.setItem(REASONING_EFFORT_KEY, value);
}

export function getCotMode(): CotMode {
  const raw = localStorage.getItem(COT_MODE_KEY);
  if (raw === "off" || raw === "strict") return raw;
  return "standard";
}

export function setCotMode(value: CotMode): void {
  localStorage.setItem(COT_MODE_KEY, value);
}

export interface ReasoningPreference {
  useServerDefault: boolean;
  enableThinking: boolean;
  reasoningEffort: ReasoningEffort;
}

export function getReasoningPreference(): ReasoningPreference {
  return {
    useServerDefault: getUseServerReasoningDefault(),
    enableThinking: getEnableThinking(),
    reasoningEffort: getReasoningEffort(),
  };
}

/** 构造 ChatRequest 中的推理字段；useServerDefault 时不发送。 */
export function buildReasoningRequestFields(
  pref: ReasoningPreference,
): Record<string, boolean | string> {
  if (pref.useServerDefault) {
    return {};
  }
  return {
    enable_thinking: pref.enableThinking,
    reasoning_effort: pref.reasoningEffort,
  };
}

export function buildCotModeRequestField(
  cotMode: CotMode,
  chatMode: ChatMode,
): Record<string, string> {
  const effective =
    chatMode === "math" && cotMode === "standard" ? "strict" : cotMode;
  return { cot_mode: effective };
}

export function getChatMode(): ChatMode {
  const raw = localStorage.getItem(CHAT_MODE_KEY);
  return raw === "math" ? "math" : "chat";
}

export function setChatMode(mode: ChatMode): void {
  localStorage.setItem(CHAT_MODE_KEY, mode);
}

export function getUseServerHistoryDefault(): boolean {
  const raw = localStorage.getItem(USE_SERVER_HISTORY_KEY);
  if (raw === null) return true;
  return raw === "true";
}

export function setUseServerHistoryDefault(value: boolean): void {
  localStorage.setItem(USE_SERVER_HISTORY_KEY, String(value));
}

export function getMaxHistoryMessages(): number {
  const raw = localStorage.getItem(MAX_HISTORY_MESSAGES_KEY);
  if (raw === null) return 0;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

export function setMaxHistoryMessages(value: number): void {
  localStorage.setItem(MAX_HISTORY_MESSAGES_KEY, String(Math.max(0, value)));
}

export function getEnableHistorySummary(): boolean {
  const raw = localStorage.getItem(ENABLE_HISTORY_SUMMARY_KEY);
  if (raw === null) return false;
  return raw === "true";
}

export function setEnableHistorySummary(value: boolean): void {
  localStorage.setItem(ENABLE_HISTORY_SUMMARY_KEY, String(value));
}

export function getUseServerMcpDefault(): boolean {
  const raw = localStorage.getItem(USE_SERVER_MCP_KEY);
  if (raw === null) return true;
  return raw === "true";
}

export function setUseServerMcpDefault(value: boolean): void {
  localStorage.setItem(USE_SERVER_MCP_KEY, String(value));
}

export function getEnableMcp(): boolean {
  const raw = localStorage.getItem(ENABLE_MCP_KEY);
  if (raw === null) return true;
  return raw === "true";
}

export function setEnableMcp(value: boolean): void {
  localStorage.setItem(ENABLE_MCP_KEY, String(value));
}

export function getAgentChoice(): AgentChoice {
  const raw = localStorage.getItem(AGENT_CHOICE_KEY);
  if (
    raw === "general" ||
    raw === "theory" ||
    raw === "experiment" ||
    raw === "literature"
  ) {
    return raw;
  }
  return "auto";
}

export function setAgentChoice(value: AgentChoice): void {
  localStorage.setItem(AGENT_CHOICE_KEY, value);
}

export interface AgentPreference {
  agent: AgentChoice;
}

export function getAgentPreference(): AgentPreference {
  return { agent: getAgentChoice() };
}

/** 构造 ChatRequest 中的 agent / auto_route 字段。 */
export function buildAgentRequestFields(
  pref: AgentPreference,
): Record<string, string | boolean> {
  if (pref.agent === "auto") {
    return { auto_route: true };
  }
  return { agent: pref.agent, auto_route: false };
}

export interface HistoryPreference {
  useServerDefault: boolean;
  maxHistoryMessages: number;
  enableHistorySummary: boolean;
}

export function getHistoryPreference(): HistoryPreference {
  return {
    useServerDefault: getUseServerHistoryDefault(),
    maxHistoryMessages: getMaxHistoryMessages(),
    enableHistorySummary: getEnableHistorySummary(),
  };
}

/** 构造 ChatRequest 中的 L1 字段；useServerDefault 时不发送（由服务端 .env 决定）。 */
export function buildHistoryRequestFields(
  pref: HistoryPreference,
): Record<string, number | boolean> {
  if (pref.useServerDefault) {
    return {};
  }
  const fields: Record<string, number | boolean> = {
    max_history_messages: pref.maxHistoryMessages,
    enable_history_summary: pref.enableHistorySummary,
  };
  return fields;
}

export interface McpPreference {
  useServerDefault: boolean;
  enableMcp: boolean;
}

export function getMcpPreference(): McpPreference {
  return {
    useServerDefault: getUseServerMcpDefault(),
    enableMcp: getEnableMcp(),
  };
}

/** 构造 ChatRequest 中的 MCP 字段；useServerDefault 时不发送（由服务端 .env 决定）。 */
export function buildMcpRequestFields(
  pref: McpPreference,
): Record<string, boolean> {
  if (pref.useServerDefault) {
    return {};
  }
  return { enable_tools: pref.enableMcp };
}
