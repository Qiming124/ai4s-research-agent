import type { ChatMessage } from "../hooks/useChatStream";
import { MarkdownContent } from "./MarkdownContent";
import { ReasoningPanel } from "./ReasoningPanel";
import { ToolTimeline } from "./ToolTimeline";

interface MessageBubbleProps {
  message: ChatMessage;
  showReasoning?: boolean;
}

const AGENT_LABELS: Record<string, string> = {
  general: "General",
  theory: "Theory",
  experiment: "Experiment",
  literature: "Literature",
  supervisor: "Supervisor",
};

function agentLabel(name: string): string {
  return AGENT_LABELS[name] ?? name;
}

export function MessageBubble({ message, showReasoning = true }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`message-row ${isUser ? "message-user" : "message-assistant"}`}>
      <div className="message-avatar">{isUser ? "你" : "AI"}</div>
      <div className="message-body">
        {isUser ? (
          <div className="user-text">{message.content}</div>
        ) : (
          <>
            {message.agentName && (
              <span className="agent-tag">{agentLabel(message.agentName)}</span>
            )}
            {message.error && (
              <div className="message-error">错误：{message.error}</div>
            )}
            <ToolTimeline timeline={message.timeline} />
            {showReasoning && (
              <ReasoningPanel
                reasoning={message.reasoning ?? ""}
                isStreaming={!!message.streaming}
              />
            )}
            <MarkdownContent content={message.content} isStreaming={!!message.streaming} />
            {message.streaming && message.content && (
              <span className="cursor-blink">▍</span>
            )}
            {message.usage && !message.streaming && (
              <div className="usage-hint">
                tokens: {String((message.usage as { total_tokens?: number }).total_tokens ?? "—")}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
