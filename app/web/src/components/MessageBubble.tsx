import type { ChatMessage } from "../hooks/useChatStream";
import { ErrorBoundary } from "./ErrorBoundary";
import { MarkdownContent } from "./MarkdownContent";
import { ReasoningPanel } from "./ReasoningPanel";
import { ToolTimeline } from "./ToolTimeline";

interface MessageBubbleProps {
  message: ChatMessage;
  showReasoning?: boolean;
}

function streamingPlaceholder(message: ChatMessage): string | null {
  if (!message.streaming) return null;
  if (message.content) return null;
  if (message.reasoning) return "正在思考…";

  const timeline = message.timeline ?? [];
  const runningTool = timeline.find(
    (entry) => entry.kind === "tool" && entry.event.status === "running",
  );
  if (runningTool && runningTool.kind === "tool") {
    return `正在调用工具：${runningTool.event.toolName}…`;
  }
  if (timeline.length > 0) return "工具执行完成，正在生成回答…";
  return "正在生成…";
}

export function MessageBubble({ message, showReasoning = true }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const placeholder = !isUser ? streamingPlaceholder(message) : null;

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
            <ToolTimeline timeline={message.timeline} />
            {showReasoning && (
              <ReasoningPanel
                reasoning={message.reasoning ?? ""}
                isStreaming={!!message.streaming}
              />
            )}
            {placeholder && (
              <div className="streaming-placeholder" aria-live="polite">
                {placeholder}
              </div>
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
