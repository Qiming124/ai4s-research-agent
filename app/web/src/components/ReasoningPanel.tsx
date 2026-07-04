import { useEffect, useRef } from "react";
import { MarkdownContent } from "./MarkdownContent";

interface ReasoningPanelProps {
  reasoning: string;
  isStreaming: boolean;
}

/** 思考过程：流式阶段纯文本；结束后 Markdown + KaTeX 渲染 */
export function ReasoningPanel({ reasoning, isStreaming }: ReasoningPanelProps) {
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isStreaming || !bodyRef.current) return;
    bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [reasoning, isStreaming]);

  if (!reasoning) return null;

  return (
    <details className="reasoning-panel" open={isStreaming || undefined}>
      <summary className="reasoning-summary">
        思考过程
        <span className="reasoning-meta">
          {reasoning.length} 字
          {isStreaming && <span className="streaming-dot"> · 生成中</span>}
        </span>
      </summary>
      <div className="reasoning-body" ref={bodyRef}>
        <MarkdownContent
          content={reasoning}
          className="reasoning-md"
          isStreaming={isStreaming}
        />
      </div>
    </details>
  );
}
