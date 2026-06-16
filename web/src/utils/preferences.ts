const SHOW_REASONING_KEY = "ai4s_show_reasoning";
const CHAT_MODE_KEY = "ai4s_chat_mode";

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
