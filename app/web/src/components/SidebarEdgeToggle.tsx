interface SidebarEdgeToggleProps {
  /** left：按钮在左栏右缘；right：按钮在右栏左缘 */
  side: "left" | "right";
  collapsed: boolean;
  onToggle: () => void;
}

/**
 * 侧边栏边缘收起/展开：
 * - 左栏展开显示 «（收起），收起显示 »（展开）
 * - 右栏展开显示 »（收起），收起显示 «（展开）
 */
export function SidebarEdgeToggle({ side, collapsed, onToggle }: SidebarEdgeToggleProps) {
  const collapseLeft = side === "left" && !collapsed;
  const expandLeft = side === "left" && collapsed;
  const collapseRight = side === "right" && !collapsed;

  let label: string;
  let symbol: string;
  if (collapseLeft) {
    label = "收起左侧栏";
    symbol = "«";
  } else if (expandLeft) {
    label = "展开左侧栏";
    symbol = "»";
  } else if (collapseRight) {
    label = "收起右侧栏";
    symbol = "»";
  } else {
    label = "展开右侧栏";
    symbol = "«";
  }

  return (
    <button
      type="button"
      className={`sidebar-edge-toggle sidebar-edge-toggle--${side}${
        collapsed ? " sidebar-edge-toggle--collapsed" : ""
      }`}
      onClick={onToggle}
      aria-expanded={!collapsed}
      aria-label={label}
      title={label}
    >
      <span className="sidebar-edge-toggle-symbol" aria-hidden="true">
        {symbol}
      </span>
    </button>
  );
}
