/** 从 Markdown 正文解析 ## 标题分节（客户端回退，与后端 cot_parser 对齐）。 */

export interface CotStep {
  step: number;
  title: string;
  body: string;
}

const SECTION_RE = /^##\s+(.+?)\s*$/gm;

export function stripCotSections(content: string): string {
  const text = content.trim();
  if (!text) return content;

  const matches = [...text.matchAll(SECTION_RE)];
  if (matches.length === 0) return content;

  let stripped = text;
  for (let i = matches.length - 1; i >= 0; i--) {
    const match = matches[i];
    const start = match.index ?? 0;
    const end =
      i + 1 < matches.length
        ? (matches[i + 1].index ?? text.length)
        : text.length;
    stripped = stripped.slice(0, start) + stripped.slice(end);
  }
  return stripped.trim();
}

export function parseCotSections(content: string): CotStep[] {
  const text = content.trim();
  if (!text) return [];

  const matches = [...text.matchAll(SECTION_RE)];
  if (matches.length === 0) return [];

  const steps: CotStep[] = [];
  matches.forEach((match, idx) => {
    const title = match[1]?.trim() ?? "";
    const start = (match.index ?? 0) + match[0].length;
    const end =
      idx + 1 < matches.length
        ? (matches[idx + 1].index ?? text.length)
        : text.length;
    const body = text.slice(start, end).trim();
    if (body) {
      steps.push({ step: idx + 1, title, body });
    }
  });
  return steps;
}
