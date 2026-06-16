const SHOW_REASONING_KEY = "ai4s_show_reasoning";
const CHAT_MODE_KEY = "ai4s_chat_mode";
const USE_SERVER_HISTORY_KEY = "ai4s_use_server_history";
const MAX_HISTORY_MESSAGES_KEY = "ai4s_max_history_messages";
const ENABLE_HISTORY_SUMMARY_KEY = "ai4s_enable_history_summary";

export type ChatMode = "chat" | "math";

export function getShowReasoning(): boolean {
  const raw = localStorage.getItem(SHOW_REASONING_KEY);
  if (raw === null) return true;
  return raw === "true";
}

export function setShowReasoning(value: boolean): void {
  localStorage.setItem(SHOW_REASONING_KEY, String(value));
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
