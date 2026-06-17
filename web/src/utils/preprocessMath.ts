/**
 * 渲染前预处理 LaTeX，修复模型常见输出问题：
 * - 裸 \begin{cases}...\end{cases} 或仅有尾部 $$
 * - 跨行 $...$ 折叠为单行 / 提升为 $$
 * - 未闭合定界符与环境
 */

/** 应使用 $$ 独立成行的 LaTeX 环境 */
const DISPLAY_ENVS = [
  "cases",
  "align",
  "aligned",
  "alignat",
  "gather",
  "multline",
  "matrix",
  "pmatrix",
  "bmatrix",
  "vmatrix",
  "Vmatrix",
  "equation",
  "split",
  "array",
] as const;

function containsDisplayEnv(latex: string): boolean {
  return DISPLAY_ENVS.some((env) => latex.includes(`\\begin{${env}}`));
}

function repairEnvironmentClosures(latex: string): string {
  let result = latex;
  for (const env of DISPLAY_ENVS) {
    const begin = `\\begin{${env}}`;
    const end = `\\end{${env}}`;
    if (!result.includes(begin) || result.includes(end)) continue;

    result = result.trimEnd();
    if (result.endsWith("&")) {
      result += " \\cdots";
    }
    result += ` \\end{${env}}`;
  }
  return result;
}

function processMathInner(latex: string, forceDisplay: boolean): string {
  const repaired = repairEnvironmentClosures(latex.trim());
  if (forceDisplay || containsDisplayEnv(repaired)) {
    return `$$${repaired}$$`;
  }
  return `$${repaired}$`;
}

function isAlreadyWrapped(content: string, start: number, end: number): boolean {
  const before2 = content.slice(Math.max(0, start - 2), start);
  // 完整块级：开头已有 $$
  if (before2 === "$$") return true;
  // 完整行内：单 $ 包裹（非 $$）
  const before1 = content.slice(Math.max(0, start - 1), start);
  const after1 = content.slice(end, end + 1);
  if (before1 === "$" && before2 !== "$$" && after1 === "$") {
    const after2 = content.slice(end, end + 2);
    if (after2 !== "$$") return true;
  }
  return false;
}

/**
 * 包裹裸 LaTeX 环境块，并修复仅有尾部 $$ 的写法：
 *   \begin{cases}...\end{cases}$$
 */
function wrapBareLatexEnvironments(content: string): string {
  let result = content;
  const replacements: { start: number; end: number; text: string }[] = [];

  for (const env of DISPLAY_ENVS) {
    const re = new RegExp(
      `\\\\begin\\{${env}\\}[\\s\\S]*?\\\\end\\{${env}\\}`,
      "g",
    );
    let match: RegExpExecArray | null;
    while ((match = re.exec(result)) !== null) {
      const blockStart = match.index;
      const blockEnd = blockStart + match[0].length;
      if (isAlreadyWrapped(result, blockStart, blockEnd)) continue;

      let consumeEnd = blockEnd;
      // 模型常漏写开头 $$，只写 \end{cases}$$
      if (result.slice(blockEnd, blockEnd + 2) === "$$") {
        consumeEnd = blockEnd + 2;
      } else if (result.slice(blockEnd, blockEnd + 1) === "$") {
        consumeEnd = blockEnd + 1;
      }

      replacements.push({
        start: blockStart,
        end: consumeEnd,
        text: `$$${match[0]}$$`,
      });
    }
  }

  replacements.sort((a, b) => b.start - a.start);
  for (const { start, end, text } of replacements) {
    result = result.slice(0, start) + text + result.slice(end);
  }
  return result;
}

/** 跨行 $...$ 折叠空白；含 cases 等环境时提升为 $$ */
function collapseMultilineInlineMath(content: string): string {
  return content.replace(/\$(?!\$)([\s\S]*?)\$(?!\$)/g, (match, inner: string) => {
    if (!inner.includes("\n")) return match;
    const collapsed = inner.replace(/\s*\n+\s*/g, " ").trim();
    return processMathInner(collapsed, containsDisplayEnv(collapsed));
  });
}

function closeUnclosedDollarDelimiters(content: string): string {
  let count = 0;
  for (let i = 0; i < content.length; i++) {
    if (content[i] === "$" && (i === 0 || content[i - 1] !== "\\")) {
      count++;
    }
  }
  return count % 2 === 1 ? content + "$" : content;
}

function processInlineDollars(content: string): string {
  return content.replace(/\$([^$\n]+?)\$/g, (_, inner: string) =>
    processMathInner(inner, false),
  );
}

function processDisplayDollars(content: string): string {
  return content.replace(/\$\$([\s\S]*?)\$\$/g, (_, inner: string) =>
    processMathInner(inner, true),
  );
}

/**
 * 对 Markdown 文本中的数学片段做预处理。
 */
export function preprocessMathContent(content: string): string {
  if (!content.includes("$") && !content.includes("\\begin{")) {
    return content;
  }

  let result = content;

  // 1. 裸环境 / 缺开头 $$
  result = wrapBareLatexEnvironments(result);

  // 2. 跨行 $...$
  result = collapseMultilineInlineMath(result);

  // 3. 标准块级与行内
  result = processDisplayDollars(result);
  result = processInlineDollars(result);

  // 4. 未闭合 $
  result = closeUnclosedDollarDelimiters(result);

  // 5. 补定界符后再扫一遍行内（可能新生成可匹配片段）
  if (result !== content) {
    result = processInlineDollars(result);
  }

  return result;
}
