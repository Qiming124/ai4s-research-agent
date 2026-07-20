import { memo } from "react";
import type { ChatMessage } from "../hooks/useChatStream";
import { parseCotSections, stripCotSections } from "../utils/cotParse";
import { CotStepsPanel } from "./CotStepsPanel";
import { ErrorBoundary } from "./ErrorBoundary";
import { MarkdownContent } from "./MarkdownContent";
import { ReasoningPanel } from "./ReasoningPanel";
import { WorkflowTimeline } from "./WorkflowTimeline";
import { LossLandscapeViz } from "./LossLandscapeViz";

interface MessageBubbleProps {
  message: ChatMessage;
  showReasoning?: boolean;
}

function streamingPlaceholder(message: ChatMessage): string | null {
  if (!message.streaming) return null;
  if (message.content) return null;
  if (message.reasoning) return "正在思考…";

  const timeline = message.timeline ?? [];
  const runningWorkflow = timeline.find(
    (entry) =>
      (entry.kind === "workflow" || entry.kind === "verify") &&
      entry.event.status === "running",
  );
  if (runningWorkflow && (runningWorkflow.kind === "workflow" || runningWorkflow.kind === "verify")) {
    return `${runningWorkflow.event.title}…`;
  }

  const runningTool = timeline.find(
    (entry) => entry.kind === "tool" && entry.event.status === "running",
  );
  if (runningTool && runningTool.kind === "tool") {
    return `正在调用工具：${runningTool.event.toolName}…`;
  }
  if (timeline.length > 0) return "工具执行完成，正在生成回答…";
  return "正在生成…";
}

function MessageBubbleInner({ message, showReasoning = true }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const placeholder = !isUser ? streamingPlaceholder(message) : null;
  const cotSteps =
    message.cotSteps && message.cotSteps.length > 0
      ? message.cotSteps
      : !message.streaming
        ? parseCotSections(message.content)
        : [];
  const displayContent =
    cotSteps.length > 0 ? stripCotSections(message.content) : message.content;

  return (
    <ErrorBoundary
      fallback={
        <div className="message-error">
          本条消息渲染失败（已跳过）
        </div>
      }
    >
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
              <WorkflowTimeline timeline={message.timeline} />
              {message.memoryWarnings?.map((w, i) => (
                <div key={i} className="memory-warning">⚠ {w}</div>
              ))}
              {message.pipelineStages && message.pipelineStages.length > 0 && (
                <div className="pipeline-stages">
                  流水线: {message.pipelineStages.join(" → ")}
                </div>
              )}
              {message.vizData && <LossLandscapeViz data={message.vizData} />}
              {showReasoning && (
                <ReasoningPanel
                  reasoning={message.reasoning ?? ""}
                  isStreaming={!!message.streaming}
                />
              )}
              <CotStepsPanel steps={cotSteps} />
              {placeholder && (
                <div className="streaming-placeholder" aria-live="polite">
                  {placeholder}
                </div>
              )}
              <MarkdownContent content={displayContent} isStreaming={!!message.streaming} />
              {message.streaming && displayContent && (
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
    </ErrorBoundary>
  );
}

export const MessageBubble = memo(MessageBubbleInner);
