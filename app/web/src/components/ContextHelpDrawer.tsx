import { useEffect, type ReactNode } from "react";
import type { HelpBlock } from "../utils/contextHelpContent";

interface ContextHelpDrawerProps {
  open: boolean;
  title: string;
  blocks: HelpBlock[];
  onClose: () => void;
  /** 可选页脚提示 */
  footer?: ReactNode;
}

/** 嵌在设置/导出区域内的小型帮助抽屉 */
export function ContextHelpDrawer({
  open,
  title,
  blocks,
  onClose,
  footer,
}: ContextHelpDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="ctx-help-layer" role="presentation">
      <button type="button" className="ctx-help-backdrop" aria-label="关闭帮助" onClick={onClose} />
      <aside className="ctx-help-drawer" role="dialog" aria-modal="true" aria-labelledby="ctx-help-title">
        <header className="ctx-help-head">
          <h3 id="ctx-help-title">{title}</h3>
          <button type="button" className="btn-small" onClick={onClose}>
            关闭
          </button>
        </header>
        <div className="ctx-help-body">
          {blocks.map((b) => (
            <section key={b.title} className="ctx-help-block">
              <h4>{b.title}</h4>
              <p>{b.body}</p>
            </section>
          ))}
        </div>
        {footer && <footer className="ctx-help-footer">{footer}</footer>}
      </aside>
    </div>
  );
}

interface ContextHelpTriggerProps {
  label?: string;
  onClick: () => void;
  disabled?: boolean;
}

export function ContextHelpTrigger({
  label = "帮助",
  onClick,
  disabled,
}: ContextHelpTriggerProps) {
  return (
    <button
      type="button"
      className="btn-link ctx-help-trigger"
      onClick={onClick}
      disabled={disabled}
      title="打开本区帮助"
    >
      {label}
    </button>
  );
}
