/**
 * 界面版本：按使用场景隐藏主导航入口（仅前端展示，不门禁 API）。
 * localStorage key: ai4s_ui_edition；默认 research（科研版）。
 */

import type { WorkbenchTab } from "./workbenchTabs";

export type UiEdition = "chat" | "research" | "full";

export type LeftSidebarTab = "sessions" | "tasks";

export interface EditionFeatures {
  leftTabs: LeftSidebarTab[];
  workbenchTabs: WorkbenchTab[];
  showWorkbench: boolean;
  /** 输入区显示「AI润色提示词」预设（对话版隐藏） */
  showAiPolishPrompts: boolean;
}

const STORAGE_KEY = "ai4s_ui_edition";

export const UI_EDITION_OPTIONS: { id: UiEdition; label: string; hint: string }[] = [
  { id: "chat", label: "对话版", hint: "仅会话与对话，隐藏科研工作台" },
  { id: "research", label: "科研版", hint: "会话树（含课题文件夹）+ 文献/理论/产出（默认）" },
  { id: "full", label: "完整版", hint: "含任务看板与验证 Tab" },
];

export const EDITION_FEATURES: Record<UiEdition, EditionFeatures> = {
  chat: {
    leftTabs: ["sessions"],
    workbenchTabs: [],
    showWorkbench: false,
    showAiPolishPrompts: false,
  },
  research: {
    leftTabs: ["sessions"],
    workbenchTabs: ["literature", "theory", "output"],
    showWorkbench: true,
    showAiPolishPrompts: true,
  },
  full: {
    leftTabs: ["sessions", "tasks"],
    workbenchTabs: ["literature", "theory", "verify", "output"],
    showWorkbench: true,
    showAiPolishPrompts: true,
  },
};

export function isUiEdition(value: string | null | undefined): value is UiEdition {
  return value === "chat" || value === "research" || value === "full";
}

export function getUiEdition(): UiEdition {
  const raw = localStorage.getItem(STORAGE_KEY);
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
