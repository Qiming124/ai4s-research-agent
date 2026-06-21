interface ReasoningPanelProps {
  reasoning: string;
  isStreaming: boolean;
}

/** 思考过程：始终纯文本，避免流结束后切换 Markdown/KaTeX 导致崩溃 */
export function ReasoningPanel({ reasoning, isStreaming }: ReasoningPanelProps) {
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
      <div className="reasoning-body">
        <pre className="reasoning-plain reasoning-md">{reasoning}</pre>
      </div>
    </details>
  );
}
