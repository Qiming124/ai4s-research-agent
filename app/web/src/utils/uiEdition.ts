/**
 * 界面版本：按使用场景隐藏主导航入口（仅前端展示，不门禁 API）。
 * localStorage key: ai4s_ui_edition；默认 research（科研版）。
 * 「完整版」已移除；历史 full 自动迁移为 research。
 */

import type { WorkbenchTab } from "./workbenchTabs";

export type UiEdition = "chat" | "research";

export type LeftSidebarTab = "sessions" | "tasks";

export interface EditionFeatures {
  leftTabs: LeftSidebarTab[];
  workbenchTabs: WorkbenchTab[];
  showWorkbench: boolean;
  /** 输入区「优化提示词」入口（含内置导出润色体例）；各版本均显示 */
  showAiPolishPrompts: boolean;
}

const STORAGE_KEY = "ai4s_ui_edition";

export const UI_EDITION_OPTIONS: { id: UiEdition; label: string; hint: string }[] = [
  { id: "chat", label: "对话版", hint: "仅会话与对话，隐藏科研工作台" },
  { id: "research", label: "科研版", hint: "会话树（含课题文件夹）+ 文献/理论/产出（默认）" },
];

export const EDITION_FEATURES: Record<UiEdition, EditionFeatures> = {
  chat: {
    leftTabs: ["sessions"],
    workbenchTabs: [],
    showWorkbench: false,
    showAiPolishPrompts: true,
  },
  research: {
    leftTabs: ["sessions"],
    workbenchTabs: ["literature", "theory", "output"],
    showWorkbench: true,
    showAiPolishPrompts: true,
  },
};

export function isUiEdition(value: string | null | undefined): value is UiEdition {
  return value === "chat" || value === "research";
}

export function getUiEdition(): UiEdition {
  const raw = localStorage.getItem(STORAGE_KEY);
  // 历史「完整版」迁移为科研版
  if (raw === "full") {
    localStorage.setItem(STORAGE_KEY, "research");
    return "research";
  }
  if (isUiEdition(raw)) return raw;
  return "research";
}

export function setUiEdition(value: UiEdition): void {
  localStorage.setItem(STORAGE_KEY, value);
}

export function getEditionFeatures(edition: UiEdition = getUiEdition()): EditionFeatures {
  return EDITION_FEATURES[edition];
}

export function clampLeftTab(edition: UiEdition, tab: LeftSidebarTab): LeftSidebarTab {
  const allowed = EDITION_FEATURES[edition].leftTabs;
  if (allowed.includes(tab)) return tab;
  return allowed[0] ?? "sessions";
}

export function clampWorkbenchTab(
  edition: UiEdition,
  tab: WorkbenchTab,
): WorkbenchTab | null {
  const feats = EDITION_FEATURES[edition];
  if (!feats.showWorkbench || feats.workbenchTabs.length === 0) return null;
  if (feats.workbenchTabs.includes(tab)) return tab;
  return feats.workbenchTabs[0] ?? null;
}
