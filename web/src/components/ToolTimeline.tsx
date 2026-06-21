import type { TimelineEntry } from "../hooks/useChatStream";

interface ToolTimelineProps {
  timeline?: TimelineEntry[];
}

function safeToolText(value: unknown, maxLen = 800): string {
  if (value == null) return "";
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
}

export function ToolTimeline({ timeline = [] }: ToolTimelineProps) {
  if (timeline.length === 0) return null;

  return (
    <div className="tool-timeline">
      <div className="tool-timeline-title">执行时间线</div>
      <ol className="tool-timeline-list">
        {timeline.map((entry) => {
          if (entry.kind === "handoff") {
            const h = entry.event;
            return (
              <li key={h.id} className="timeline-item timeline-handoff">
                <span className="timeline-dot timeline-dot-handoff" aria-hidden />
                <div className="timeline-content">
                  <div className="timeline-header">
                    <span className="timeline-label">Agent 切换</span>
                  </div>
                  <div className="handoff-route">
                    <span className="handoff-agent">{h.fromAgent}</span>
                    <span className="handoff-arrow">→</span>
                    <span className="handoff-agent handoff-agent-target">{h.toAgent}</span>
                  </div>
                  {h.reason && <p className="handoff-reason">{h.reason}</p>}
                </div>
              </li>
            );
          }

          const ev = entry.event;
          return (
            <li key={ev.id} className={`timeline-item timeline-tool tool-call-${ev.status}`}>
              <span className={`timeline-dot timeline-dot-${ev.status}`} aria-hidden />
              <div className="timeline-content">
                <div className="timeline-header">
                  <code className="tool-call-name">{ev.toolName}</code>
                  <span className="tool-call-status">
                    {ev.status === "running" ? "执行中…" : ev.status === "error" ? "失败" : "完成"}
                  </span>
                </div>
                {ev.arguments != null && ev.arguments !== "" && (
                  <pre className="tool-call-args">{safeToolText(ev.arguments, 400)}</pre>
                )}
                {ev.result != null && ev.result !== "" && (
                  <pre className="tool-call-result">{safeToolText(ev.result)}</pre>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
