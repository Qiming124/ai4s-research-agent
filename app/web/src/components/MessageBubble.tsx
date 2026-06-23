import type { ChatMessage } from "../hooks/useChatStream";
import { ErrorBoundary } from "./ErrorBoundary";
import { MarkdownContent } from "./MarkdownContent";
import { ReasoningPanel } from "./ReasoningPanel";

interface MessageBubbleProps {
  message: ChatMessage;
  showReasoning?: boolean;
}

export function MessageBubble({ message, showReasoning = true }: MessageBubbleProps) {
  const isUser = message.role === "user";

  const body = (
    <div className={`message-row ${isUser ? "message-user" : "message-assistant"}`}>
      <div className="message-avatar">{isUser ? "你" : "AI"}</div>
      <div className="message-body">
        {isUser ? (
          <div className="user-text">{message.content}</div>
        ) : (
          <>
            {message.error && (
              <div className="message-error">错误：{message.error}</div>
            )}
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

  return (
    <ErrorBoundary
      fallback={
        <div className="message-error">
          本条消息渲染失败（已跳过）
        </div>
      }
    >
      {body}
    </ErrorBoundary>
  );
}
