import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import { MarkdownContent } from "./MarkdownContent";

export type TheoremStatus =
  | "draft"
  | "symbolically_verified"
  | "numerically_verified"
  | "experiment_verified"
  | "proved"
  | "refuted";

export function getEntryStatus(entry: StructuredMemoryEntry): TheoremStatus {
  const status = (entry.metadata?.status as string) || "draft";
  if (
    status === "symbolically_verified" ||
    status === "numerically_verified" ||
    status === "experiment_verified" ||
    status === "proved" ||
    status === "refuted"
  ) {
    return status as TheoremStatus;
  }
  return "draft";
}

const STATUS_LABELS: Record<TheoremStatus, string> = {
  draft: "草稿",
  symbolically_verified: "符号验证",
  numerically_verified: "数值验证",
  experiment_verified: "实验支持",
  proved: "已证实",
  refuted: "反例",
};

interface StatusBadgeProps {
  status: TheoremStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`status-badge status-${status}`}>{STATUS_LABELS[status]}</span>;
}

interface TheoremDetailDrawerProps {
  entry: StructuredMemoryEntry | null;
  onClose: () => void;
  onCreateTask?: (title: string, entryId: number) => Promise<void>;
}

export function TheoremDetailDrawer({ entry, onClose, onCreateTask }: TheoremDetailDrawerProps) {
  if (!entry) return null;
  const status = getEntryStatus(entry);
  const ledger = (entry.metadata?.verification_ledger as unknown[]) ?? [];

  return (
    <div className="theorem-drawer-overlay" onClick={onClose} role="presentation">
      <aside
        className="theorem-drawer"
        onClick={(e) => e.stopPropagation()}
        aria-label="定理详情"
      >
        <header className="theorem-drawer-header">
          <div>
            <StatusBadge status={status} />
            <h3>{entry.title || `条目 #${entry.id}`}</h3>
            <span className="theorem-kind-tag">{entry.kind}</span>
          </div>
          <button type="button" className="btn-small" onClick={onClose}>
            关闭
          </button>
        </header>
        <div className="theorem-drawer-body">
          <MarkdownContent content={entry.body} className="panel-markdown theorem-full-body" />
          {Array.isArray(ledger) && ledger.length > 0 && (
            <section>
              <h4>验证记录</h4>
              <ul className="verification-ledger-list">
                {ledger.map((item, i) => (
                  <li key={i}>
                    <code>{JSON.stringify(item).slice(0, 200)}</code>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigator.clipboard.writeText(entry.body)}
          >
            复制正文
          </button>
          {onCreateTask && entry.id != null && (
            <button
              type="button"
              className="btn-primary"
              onClick={() =>
                void onCreateTask(
                  `跟进：${entry.title || `定理 #${entry.id}`}`,
                  entry.id as number,
                )
              }
            >
              生成课题任务
            </button>
          )}
        </div>
      </aside>
    </div>
  );
}
