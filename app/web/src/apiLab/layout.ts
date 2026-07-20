/**
 * API 实验室三栏宽度：localStorage 持久化。
 */

const STORAGE_KEY = "ai4s_api_lab_layout";

export interface ApiLabLayout {
  catalogWidth: number;
  editorWidth: number;
}

const DEFAULT: ApiLabLayout = {
  catalogWidth: 260,
  editorWidth: 420,
};

const CATALOG_MIN = 180;
const CATALOG_MAX = 420;
const EDITOR_MIN = 280;
const EDITOR_MAX = 720;

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

export function loadApiLabLayout(): ApiLabLayout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT };
    const parsed = JSON.parse(raw) as Partial<ApiLabLayout>;
    return {
      catalogWidth: clamp(
        Number(parsed.catalogWidth) || DEFAULT.catalogWidth,
        CATALOG_MIN,
        CATALOG_MAX,
      ),
      editorWidth: clamp(
        Number(parsed.editorWidth) || DEFAULT.editorWidth,
        EDITOR_MIN,
        EDITOR_MAX,
      ),
    };
  } catch {
    return { ...DEFAULT };
  }
}

export function saveApiLabLayout(layout: ApiLabLayout): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
}

export function adjustCatalogWidth(current: number, delta: number): number {
  return clamp(current + delta, CATALOG_MIN, CATALOG_MAX);
}

export function adjustEditorWidth(current: number, delta: number): number {
  return clamp(current + delta, EDITOR_MIN, EDITOR_MAX);
}
