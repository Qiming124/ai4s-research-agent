import { memo, useState, type KeyboardEvent } from "react";
import type { AgentChoice, ChatMode } from "../utils/preferences";
import { PromptOptimizerPanel } from "./PromptOptimizerPanel";

interface ChatComposerProps {
  chatMode: ChatMode;
  agentChoice?: AgentChoice;
  disabled?: boolean;
  /** 仅禁用发送（流式中） */
  sendDisabled?: boolean;
  onSend: (text: string) => void | Promise<void>;
  /** 采用导出润色体例后的附加动作（如切到产出 Tab） */
  onPolishPresetSelected?: (presetId: string) => void;
}

/**
 * 输入区独立持有草稿状态，避免每个按键触发 ChatPage 整页重渲染。
 */
function ChatComposerInner({
  chatMode,
  agentChoice = "auto",
  disabled = false,
  sendDisabled = false,
  onSend,
  onPolishPresetSelected,
}: ChatComposerProps) {
  const [draft, setDraft] = useState("");
  const [optimizerOpen, setOptimizerOpen] = useState(false);
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

  return (
    <footer className="chat-footer">
      <button
        type="button"
        className="btn-secondary polish-optimize-btn"
        onClick={() => setOptimizerOpen(true)}
        disabled={disabled || sendDisabled}
        title="优化提示词：含 AI 多风格对比与导出润色体例"
      >
        优化提示词
      </button>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入问题… Enter 发送，Shift+Enter 换行；点「优化提示词」可改写或选用导出体例"
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
      <PromptOptimizerPanel
        open={optimizerOpen}
        initialText={draft}
        mode={chatMode}
        agent={agentChoice}
        onClose={() => setOptimizerOpen(false)}
        onApply={(text) => setDraft(text)}
        onPolishPresetSelected={onPolishPresetSelected}
      />
    </footer>
  );
}

export const ChatComposer = memo(ChatComposerInner);
