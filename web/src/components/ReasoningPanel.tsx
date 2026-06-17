import { useEffect, useState } from "react";
import { MarkdownContent } from "./MarkdownContent";

interface ReasoningPanelProps {
  reasoning: string;
  isStreaming: boolean;
}

/** 可折叠的思考过程面板；流式时默认展开 */
export function ReasoningPanel({ reasoning, isStreaming }: ReasoningPanelProps) {
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (isStreaming) setOpen(true);
  }, [isStreaming]);

  if (!reasoning) return null;

  return (
    <details
      className="reasoning-panel"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="reasoning-summary">
        思考过程
        <span className="reasoning-meta">
          {reasoning.length} 字
          {isStreaming && <span className="streaming-dot"> · 生成中</span>}
        </span>
      </summary>
      <div className="reasoning-body">
        <MarkdownContent content={reasoning} className="reasoning-md" isStreaming={isStreaming} />
      </div>
    </details>
  );
}
