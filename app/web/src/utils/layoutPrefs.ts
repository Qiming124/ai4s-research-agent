export interface LayoutPrefs {
  leftWidth: number;
  rightWidth: number;
  sidebarProjectHeight: number;
  sidebarTaskHeight: number;
  /** 左侧边栏是否收起；默认展开，仅存客户端 */
  leftCollapsed: boolean;
  /** 右侧边栏是否收起；默认展开，仅存客户端 */
  rightCollapsed: boolean;
}

const STORAGE_KEY = "ai4s_layout_prefs";

/** 收起后边缘开关条宽度（px）；中间栏会占用其余空间 */
export const SIDEBAR_EDGE_WIDTH = 28;

/** @deprecated 使用 SIDEBAR_EDGE_WIDTH */
export const LEFT_SIDEBAR_RAIL_WIDTH = SIDEBAR_EDGE_WIDTH;

export const DEFAULT_LAYOUT: LayoutPrefs = {
  leftWidth: 240,
  rightWidth: 380,
  sidebarProjectHeight: 130,
  sidebarTaskHeight: 200,
  leftCollapsed: false,
  rightCollapsed: false,
};

const LIMITS = {
  leftWidth: [160, 440] as const,
  rightWidth: [260, 560] as const,
  sidebarProjectHeight: [72, 300] as const,
  sidebarTaskHeight: [100, 380] as const,
};

function clamp(value: number, [min, max]: readonly [number, number]): number {
  return Math.min(max, Math.max(min, value));
}

export function loadLayoutPrefs(): LayoutPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_LAYOUT };
    const parsed = JSON.parse(raw) as Partial<LayoutPrefs>;
    return {
      leftWidth: clamp(Number(parsed.leftWidth) || DEFAULT_LAYOUT.leftWidth, LIMITS.leftWidth),
      rightWidth: clamp(Number(parsed.rightWidth) || DEFAULT_LAYOUT.rightWidth, LIMITS.rightWidth),
      sidebarProjectHeight: clamp(
        Number(parsed.sidebarProjectHeight) || DEFAULT_LAYOUT.sidebarProjectHeight,
        LIMITS.sidebarProjectHeight,
      ),
      sidebarTaskHeight: clamp(
        Number(parsed.sidebarTaskHeight) || DEFAULT_LAYOUT.sidebarTaskHeight,
        LIMITS.sidebarTaskHeight,
      ),
      leftCollapsed: Boolean(parsed.leftCollapsed),
      rightCollapsed: Boolean(parsed.rightCollapsed),
    };
  } catch {
    return { ...DEFAULT_LAYOUT };
  }
}

export function saveLayoutPrefs(prefs: LayoutPrefs): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

export function adjustLayoutPrefs(
  prefs: LayoutPrefs,
  patch: Partial<LayoutPrefs>,
): LayoutPrefs {
  const next: LayoutPrefs = { ...prefs };
  if (patch.leftWidth != null) {
    next.leftWidth = clamp(patch.leftWidth, LIMITS.leftWidth);
  }
  if (patch.rightWidth != null) {
    next.rightWidth = clamp(patch.rightWidth, LIMITS.rightWidth);
  }
  if (patch.sidebarProjectHeight != null) {
    next.sidebarProjectHeight = clamp(patch.sidebarProjectHeight, LIMITS.sidebarProjectHeight);
  }
  if (patch.sidebarTaskHeight != null) {
    next.sidebarTaskHeight = clamp(patch.sidebarTaskHeight, LIMITS.sidebarTaskHeight);
  }
  if (patch.leftCollapsed != null) {
    next.leftCollapsed = Boolean(patch.leftCollapsed);
  }
  if (patch.rightCollapsed != null) {
    next.rightCollapsed = Boolean(patch.rightCollapsed);
  }
  saveLayoutPrefs(next);
  return next;
}

export function resetLayoutPrefs(): LayoutPrefs {
  saveLayoutPrefs(DEFAULT_LAYOUT);
  return { ...DEFAULT_LAYOUT };
}
