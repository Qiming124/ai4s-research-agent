import { useState, type ReactNode } from "react";

interface WorkbenchSectionProps {
  title: string;
  defaultOpen?: boolean;
  badge?: string | number;
  children: ReactNode;
}

export function WorkbenchSection({
  title,
  defaultOpen = false,
  badge,
  children,
}: WorkbenchSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={`workbench-section${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="workbench-section-head"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="workbench-section-title">{title}</span>
        {badge != null && badge !== "" && (
          <span className="workbench-section-badge">{badge}</span>
        )}
        <span className="workbench-section-chevron" aria-hidden>
          {open ? "−" : "+"}
        </span>
      </button>
      {open && <div className="workbench-section-body">{children}</div>}
    </section>
  );
}
