import { memo, useState, type KeyboardEvent } from "react";
import type { ChatMode } from "../utils/preferences";
import {
  POLISH_PRESETS,
  dispatchExportPreset,
} from "../utils/exportPresets";

interface ChatComposerProps {
  chatMode: ChatMode;
  onChatModeChange: (mode: ChatMode) => void;
  /** 显示「AI润色提示词」预设选择（原完整研究入口） */
  showAiPolishPrompts?: boolean;
  disabled?: boolean;
  /** 仅禁用发送（流式中） */
  sendDisabled?: boolean;
  onSend: (text: string) => void | Promise<void>;
  /** 选中润色预设后的附加动作（如切到导出 Tab） */
  onPolishPresetSelected?: (presetId: string) => void;
}

/**
 * 输入区独立持有草稿状态，避免每个按键触发 ChatPage 整页重渲染。
 */
function ChatComposerInner({
  chatMode,
  onChatModeChange,
  showAiPolishPrompts = false,
  disabled = false,
  sendDisabled = false,
  onSend,
  onPolishPresetSelected,
}: ChatComposerProps) {
  const [draft, setDraft] = useState("");
  const [presetId, setPresetId] = useState("");
  const inputLocked = disabled || sendDisabled;

  const submit = () => {
    const text = draft.trim();
    if (!text || inputLocked) return;
    setDraft("");
    void onSend(text);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const applyPreset = (id: string) => {
    setPresetId(id);
    if (!id) return;
    const preset = POLISH_PRESETS.find((p) => p.id === id);
    if (!preset) return;
    setDraft(
      `请按以下「${preset.label}」体例，润色整理当前课题/会话中的定理、推导与结论：\n\n${preset.text}`,
    );
    dispatchExportPreset(id);
    onPolishPresetSelected?.(id);
  };

  return (
    <footer className="chat-footer">
      <div className="mode-toggle footer-mode-toggle" role="group">
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
      {showAiPolishPrompts && (
        <label className="polish-preset-select-wrap" title="填入导出同款 AI 润色提示词，并可同步到产出 Tab">
          <span className="visually-hidden">AI润色提示词</span>
          <select
            className="polish-preset-select"
            value={presetId}
            disabled={disabled}
            aria-label="AI润色提示词"
            onChange={(e) => applyPreset(e.target.value)}
          >
            <option value="">AI润色提示词…</option>
            {POLISH_PRESETS.map((p) => (
              <option key={p.id} value={p.id} title={p.hint}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
      )}
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入问题… Enter 发送，Shift+Enter 换行；可用「AI润色提示词」填入体例"
        rows={2}
        disabled={inputLocked}
      />
      <button
        type="button"
        className="btn-primary"
        onClick={submit}
        disabled={inputLocked || !draft.trim()}
      >
        发送
      </button>
    </footer>
  );
}

export const ChatComposer = memo(ChatComposerInner);
