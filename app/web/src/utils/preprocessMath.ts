/**
 * 渲染前预处理 LaTeX，修复模型常见输出问题：
 * - 裸 \begin{cases}...\end{cases} 或仅有尾部 $$
 * - 跨行 $...$ 折叠为单行 / 提升为 $$
 * - 模型误用 {sub} 代替 _{sub}、漏写下标 _
 * - 未闭合定界符与环境；多余 $ 定界符
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

const DISPLAY_ENVS_LONGEST_FIRST = [...DISPLAY_ENVS].sort(
  (a, b) => b.length - a.length,
);

/** 行内 $ 定界符：不匹配 $$ 块级 */
const INLINE_DOLLAR_RE = /(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g;

const SUBSCRIPT_OPERATOR_CMDS =
  "sum|prod|int|oint|lim|max|min|sup|inf|det|dim|gcd|hom|ker|lg|ln|log|exp|Pr";

const GREEK_SUBSCRIPT_WORDS =
  "lambda|alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|varphi|chi|psi|omega|nabla|partial|ell";

const SINGLE_ARG_MATH_CMDS =
  "boldsymbol|mathcal|mathbf|mathrm|mathit|mathsf|mathbb|mathfrak|operatorname|hat|bar|tilde|vec|overline|underline";

const DISPLAY_BEGIN_PATTERN =
  "\\\\begin\\{(?:cases|aligned|align|gather|alignat|matrix|pmatrix|bmatrix)\\}";

/** Unicode 希腊字母（模型常直接输出 θ、λ 等） */
const UNICODE_GREEK = "θλσμναβγδϵεζηικξπρστυφχψωΘΛΣΜ";

/** 含 Unicode 数学符号 */
const UNICODE_MATH_RE = /[θλσμναβγδϵεζηικξπρστυφχψωℓ∥‖∑∏√∞±≤≥≠₀₁₂₃₄₅₆₇₈₉]/;

function containsDisplayEnv(latex: string): boolean {
  return DISPLAY_ENVS.some((env) => latex.includes(`\\begin{${env}}`));
}

function containsLatex(content: string): boolean {
  return (
    content.includes("$") ||
    content.includes("\\begin{") ||
    /\\[a-zA-Z]+/.test(content)
  );
}

function repairEnvironmentClosures(latex: string): string {
  let result = latex;
  for (const env of DISPLAY_ENVS_LONGEST_FIRST) {
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
  if (before2 === "$$") return true;
  const before1 = content.slice(Math.max(0, start - 1), start);
  const after1 = content.slice(end, end + 1);
  if (before1 === "$" && before2 !== "$$" && after1 === "$") {
    const after2 = content.slice(end, end + 2);
    if (after2 !== "$$") return true;
  }
  return false;
}

/** 连续 3 个及以上 $ 规范为 $$；将粘连在块级公式后的 \\square 移出 */
function normalizeDollarRuns(content: string): string {
  let result = content.replace(/\${3,}/g, () => "$$");
  result = result.replace(
    /\$\$([\s\S]+?)\$\$\s*\\square\b/g,
    (_, inner: string) => `$$${inner}$$\n\n$\\square$`,
  );
  return result;
}

/** 模型用 \sum{m} 代替 \sum_{m}、\lambda{\max} 代替 \lambda_{\max} 等 */
function fixMalformedSubscripts(content: string): string {
  let result = content;

  result = result.replace(
    new RegExp(`\\\\(${SUBSCRIPT_OPERATOR_CMDS})\\{`, "g"),
    "\\$1_{",
  );

  result = result.replace(
    new RegExp(`\\\\(${GREEK_SUBSCRIPT_WORDS})\\{([^}{]+)\\}(?!_)`, "g"),
    (match, cmd: string, sub: string) => {
      if (cmd === "theta" && sub.length === 1 && sub === sub.toUpperCase()) {
        return match;
      }
      if (/^(\\[a-zA-Z]+|[a-zA-Z][\w\s^_{}!-]*)$/.test(sub) && !sub.includes("\\begin")) {
        return `\\${cmd}_{${sub}}`;
      }
      return match;
    },
  );

  result = result.replace(
    new RegExp(`\\\\(${SINGLE_ARG_MATH_CMDS})\\{([^}]+)\\}\\{([^}]+)\\}`, "g"),
    "\\$1{$2}_{$3}",
  );

  result = result.replace(
    /\\(hat|bar|tilde|vec|dot|ddot)\{([^}]+)\}([a-zA-Z0-9])(?![a-zA-Z0-9_{])/g,
    "\\$1{$2}_$3",
  );

  result = result.replace(
    /\\(boldsymbol|mathcal|mathbf|mathrm)\{([^}]+)\}([a-zA-Z0-9])(?![a-zA-Z0-9_{])/g,
    "\\$1{$2}_$3",
  );

  // L{\text{MSE}}、L{\mathrm{MSE}} 等漏写 _ 的下标
  result = result.replace(
    /([A-Za-z])\{(\\(?:text|mathrm|mathbf|mathcal)\{[^}]+\})\}/g,
    "$1_{$2}",
  );

  // \hat_{\mathbf{y}} → \hat{\mathbf{y}}（装饰符与下标顺序颠倒）
  result = result.replace(
    /\\(hat|bar|tilde|vec)_\{((?:\\mathbf|\\mathcal|\\mathbb|\\mathrm)\{[^}]+\})\}/g,
    "\\$1{$2}",
  );

  return result;
}

/** cases/aligned 环境内误用单反斜杠换行 */
function fixEnvRowSeparators(content: string): string {
  return content.replace(
    /\\begin\{(cases|aligned|align)\}([\s\S]*?)\\end\{\1\}/g,
    (_, env: string, inner: string) => {
      let fixed = inner;
      if (env === "cases") {
        fixed = fixed.replace(/&([^&\n]*?)\s+\\\s+(-)/g, "&$1 \\\\ $2");
      } else {
        fixed = fixed.replace(/\s+\\\s+&/g, " \\\\ &");
      }
      return `\\begin{${env}}${fixed}\\end{${env}}`;
    },
  );
}

function isCorruptMashedGradientBlock(inner: string): boolean {
  return (
    /\\nabla_\{\\mathbf\{w\}\}/.test(inner) &&
    /\\frac\{\\partial\s+L/.test(inner) &&
    /\\partial\s+b/.test(inner)
  );
}

/** 删除文档开头粘连的错误 display 块（nabla + partial 混排并以 ** 结尾） */
function removeCorruptMashedDisplayPrefix(content: string): string {
  let result = content.replace(/^\uFEFF/, "");

  // 未闭合、以 ** 结尾的损坏块
  result = result.replace(
    /^\s*\$\$[\s\S]*?\\nabla_\{\\mathbf\{w\}\}[\s\S]*?\*\*[\s\r\n]*/m,
    "",
  );

  // 已闭合的损坏块（两条公式拼在一起）
  result = result.replace(
    /^\s*\$\$[\s\S]*?\\nabla_\{\\mathbf\{w\}\}[\s\S]*?\\partial\s+b[\s\S]*?\$\$[\s\r\n]*/m,
    "",
  );

  // 兜底：开头 $$ 到「令 / 对参数 / 中文段落」之间的 nabla_w 块
  const trimmed = result.trimStart();
  if (/^\$\$[\s\S]*?\\nabla_\{\\mathbf\{w\}\}/.test(trimmed)) {
    const proseIdx = trimmed.search(/\n\n+(?:令|对参数|写成)|(?:\r?\n){2,}[\u4e00-\u9fff#]/);
    if (proseIdx > 0) {
      result = trimmed.slice(proseIdx).trimStart();
    }
  }

  return result;
}

/** 未闭合的 $$ 在正文/加粗前强制闭合，并去掉尾部 ** */
function repairUnclosedDisplayBlocks(content: string): string {
  return content.replace(
    /\$\$([\s\S]*?)(?=\s*\*\*\s*\r?\n|\n\n+(?:令|写成|对|[\u4e00-\u9fff#]))/g,
    (match, inner: string, offset: number, str: string) => {
      if (inner.includes("$$")) return match;
      const opensBefore = (str.slice(0, offset).match(/\$\$/g) || []).length;
      if (opensBefore % 2 === 1) return match;
      const cleaned = inner.replace(/\s*\*{1,2}\s*$/, "").trimEnd();
      if (isCorruptMashedGradientBlock(cleaned)) return "";
      return `$$${cleaned}$$`;
    },
  );
}

/** 最终清理：去掉仍留在文首的损坏梯度块 */
function stripLeadingCorruptDisplayBlocks(content: string): string {
  let result = content.trimStart();
  let prev = "";
  while (prev !== result) {
    prev = result;
    result = result.replace(
      /^\$\$[\s\S]*?\\nabla_\{\\mathbf\{w\}\}[\s\S]*?\$\$\s*(?:\r?\n)*/m,
      (block) => (isCorruptMashedGradientBlock(block) ? "" : block),
    );
    result = result.replace(
      /^\$\$[\s\S]*?\\nabla_\{\\mathbf\{w\}\}[\s\S]*?\*\*[\s\r\n]*/m,
      "",
    );
  }
  return result;
}

/** 相邻重复短句（如「代入得：代入得：」） */
function dedupeAdjacentPhrases(content: string): string {
  return content
    .replace(/(代入得：)\s*\1+/g, "$1")
    .replace(/(和学习率)\s*\1+/g, "$1");
}

/** Markdown 标题与正文粘连时插入换行 */
function countDisplayOpensBefore(content: string, index: number): number {
  return (content.slice(0, index).match(/\$\$/g) || []).length;
}

/** 块级 $$ 与中文/加粗粘连时：若 $$ 用于闭合未结束的 display，则保留 */
function separateGluedAfterDisplay(
  content: string,
  pattern: RegExp,
): string {
  return content.replace(pattern, (_match, word: string, offset: number, str: string) => {
    if (countDisplayOpensBefore(str, offset) % 2 === 1) {
      return `$$\n\n${word}`;
    }
    return `\n\n${word}`;
  });
}

function separateGluedMarkdown(content: string): string {
  let result = content.replace(/([^\n#])(#{1,6}\s)/g, "$1\n\n$2");
  result = result.replace(/(\\square)(#{1,6}\s)/g, "$1\n\n$2");
  result = result.replace(/(\\end\{(?:cases|aligned|align)\}\$\$)([^\s\n$\\])/g, "$1\n\n$2");
  result = result.replace(/(\\end\{(?:cases|aligned|align)\}\$\$)(\*\*)/g, "$1\n\n$2");
  result = result.replace(/(\$\$\\square\$)(\*\*)/g, "$1\n\n$2");
  result = separateGluedAfterDisplay(
    result,
    /\$\$(其中|令|因子|即|故|则)/g,
  );
  result = separateGluedAfterDisplay(result, /\$\$([\u4e00-\u9fff])/g);
  result = separateGluedAfterDisplay(result, /\$\$(\*\*)/g);
  return result;
}

/**
 * 合并被 $$ 拆开的块级公式与环境，例如：
 *   $$\partial |\theta_j| =$$\begin{cases}...  →  $$...= \begin{cases}...
 *   $$h_j' =$$\begin{cases}...
 */
function isInsideDisplayMath(content: string, index: number): boolean {
  const before = content.slice(0, index);
  return ((before.match(/\$\$/g) || []).length % 2) === 1;
}

function mergeSplitDisplayMath(content: string): string {
  let result = content;
  result = result.replace(
    new RegExp(`\\$\\$([^$\\n\u4e00-\u9fff=]{0,120}?)\\=\\s*\\$\\$\\s*(${DISPLAY_BEGIN_PATTERN})`, "g"),
    (_, left: string, begin: string) => `$$${left.trimEnd()} = ${begin}`,
  );
  result = result.replace(
    new RegExp(`\\$(?!\\$)([^$\\n]+?)\\=\\s*\\$\\$\\s*(${DISPLAY_BEGIN_PATTERN})`, "g"),
    (_, left: string, begin: string) => `$$${left.trim()} = ${begin}`,
  );
  // $h_j' = \begin{cases}...（行内 $ 前缀 + 裸 cases 环境）
  result = result.replace(
    /(?<!\$)\$([^$\n]+=\s*)(\\begin\{cases\}[\s\S]*?\\end\{cases\})/g,
    (_, left: string, cases: string) => `$$${left}${cases}$$`,
  );
  // 裸文本 =$$\\begin{cases}（无行内 $ 或块级 $$ 前缀）
  result = result.replace(
    new RegExp(
      `(^|[^\\$\\n])([^\\$\\n=]+?)\\=\\s*\\$\\$\\s*(${DISPLAY_BEGIN_PATTERN})`,
      "gm",
    ),
    (match, prefix: string, left: string, begin: string) => {
      if (left.includes("\\begin{") || left.trim().length > 80) return match;
      return `${prefix}$$${left.trim()} = ${begin}`;
    },
  );
  result = result.replace(
    new RegExp(`\\$\\$([^$\\n\u4e00-\u9fff]{0,120}?)\\$\\$\\s*(${DISPLAY_BEGIN_PATTERN})`, "g"),
    (match, left: string, begin: string) => {
      if (left.includes("\\begin{")) return match;
      return `$$${left.trim()} ${begin}`;
    },
  );
  return result;
}

/** 模型偶发重复输出连续的 \\begin{aligned} */
function dedupeConsecutiveAlignedBegin(content: string): string {
  let result = content;
  let prev = "";
  while (prev !== result) {
    prev = result;
    result = result.replace(
      /\\begin\{aligned\}\s*\n\s*\\begin\{aligned\}/g,
      "\\begin{aligned}",
    );
  }
  return result;
}

/** 仅有 \end{aligned}$$、缺 \begin{aligned} 时补全开块 */
function fixOrphanAlignedEnd(content: string): string {
  return content.replace(
    /(^|[^\$])((?:[^\n]*&[^\n]*(?:\\\\)?\n?)+)\s*\\end\{aligned\}\$\$/gm,
    (match, prefix: string, body: string, offset: number, str: string) => {
      const throughEnd = str.slice(0, offset + match.length);
      if (throughEnd.includes("\\begin{aligned}")) return match;
      if (!body.includes("&") && !body.includes("\\\\")) return match;
      return `${prefix}$$\\begin{aligned}\n${body.trim()}\n\\end{aligned}$$`;
    },
  );
}

function wrapInInlineMath(latex: string): string {
  return `$${latex}$`;
}

function isInsideMathDelimiter(content: string, index: number): boolean {
  let inDisplay = false;
  let inInline = false;
  for (let i = 0; i < index; i++) {
    if (content[i] !== "$" || (i > 0 && content[i - 1] === "\\")) continue;
    if (content[i + 1] === "$") {
      inDisplay = !inDisplay;
      inInline = false;
      i++;
      continue;
    }
    if (!inDisplay) {
      inInline = !inInline;
    }
  }
  return inDisplay || inInline;
}

function wrapSegmentMatch(
  segment: string,
  re: RegExp,
  wrap: (match: string) => string,
): string {
  return segment.replace(re, (m, ...args: unknown[]) => {
    const offset = args[args.length - 2] as number;
    if (isInsideMathDelimiter(segment, offset)) return m;
    if (offset > 0 && segment[offset - 1] === "$") return m;
    if (segment[offset + m.length] === "$") return m;
    return wrap(m);
  });
}

/** 为正文中的裸 LaTeX / Unicode 数学补 $ 定界符，避免 GFM 把 L_0 等拆成斜体 */
function wrapProseSegmentInner(segment: string): string {
  if (/\\begin\{/.test(segment)) {
    return segment;
  }

  let s = segment;

  // 完整 \frac{}{} 优先整体包裹，避免拆碎分子分母内的 \partial 等
  s = wrapSegmentMatch(
    s,
    /\\frac\{(?:[^{}]|\{[^{}]*\})*\}\{(?:[^{}]|\{[^{}]*\})*\}/g,
    wrapInInlineMath,
  );

  // 较长裸 LaTeX 表达式优先整体包裹
  s = wrapSegmentMatch(
    s,
    /\\mathbb\{E\}\[[^\]]+\]\s*=\s*[^。]+/g,
    wrapInInlineMath,
  );
  s = wrapSegmentMatch(
    s,
    /\\mathcal\{[A-Za-z]\}\s*=\s*\\\{(?:[^{}]|\{[^{}]*\})*\\\}/g,
    wrapInInlineMath,
  );
  s = wrapSegmentMatch(
    s,
    /\\eta_t\s*=\s*[^，。\n]+/g,
    wrapInInlineMath,
  );
  s = wrapSegmentMatch(
    s,
    /\\epsilon\s*>\s*0/g,
    wrapInInlineMath,
  );

  // Unicode 下标数字：L₀、θ₁
  s = wrapSegmentMatch(
    s,
    /(?<![A-Za-z$])([A-Za-z])([₀₁₂₃₄₅₆₇₈₉]+)/g,
    wrapInInlineMath,
  );

  // Unicode 范数：∥θ∥_2、‖θ‖_2
  s = wrapSegmentMatch(
    s,
    /[∥‖]([θλσμναβγδϵε]+)[∥‖]_(\{[^}]+\}|[0-9a-zA-Z+]+)/g,
    wrapInInlineMath,
  );

  // Unicode ℓ_2
  s = wrapSegmentMatch(s, /ℓ_(\{[^}]+\}|[0-9a-zA-Z+]+)/g, wrapInInlineMath);

  // Unicode 希腊字母下标/上标：θ_MAP、λ_max、σ^2
  s = wrapSegmentMatch(
    s,
    new RegExp(`([${UNICODE_GREEK}])_([A-Za-z0-9]+)`, "g"),
    wrapInInlineMath,
  );
  s = wrapSegmentMatch(
    s,
    new RegExp(`([${UNICODE_GREEK}])\\^([0-9a-zA-Z+]+)`, "g"),
    wrapInInlineMath,
  );

  // argmax_θ、min_λ
  s = wrapSegmentMatch(
    s,
    new RegExp(`\\b(argmax|argmin|max|min)_([${UNICODE_GREEK}])\\b`, "g"),
    wrapInInlineMath,
  );

  // 嵌套花括号下标：L_{\text{MSE}}、H_{\boldsymbol{\theta}}
  s = wrapSegmentMatch(
    s,
    /\b([A-Za-z])_\{((?:[^{}]|\{[^{}]*\})+)\}/g,
    wrapInInlineMath,
  );

  // 范数：\|\theta\|_2^2、\|\nabla L(\theta)\|^2
  s = wrapSegmentMatch(
    s,
    /\\\|([^|]+?)\\\|(?:_\{[^}]+\}|_[0-9a-zA-Z+]+|\^[0-9a-zA-Z+{}]+)*/g,
    wrapInInlineMath,
  );

  // 先包裹简单下标（y_m、L_0(\theta)），避免后续 \sum 等命令被误匹配
  s = wrapSegmentMatch(
    s,
    /(?<![\\a-zA-Z$])\b([A-Za-z]{1,2})_(\{[^}]+\}|[0-9a-zA-Z+])(?:\([^)]*\))?/g,
    wrapInInlineMath,
  );

  s = wrapSegmentMatch(s, /\\sum_\{[^}]+\}/g, wrapInInlineMath);
  s = wrapSegmentMatch(
    s,
    /\\(?:lambda|theta|sigma|mu|eta|alpha|beta|gamma|delta|epsilon|partial|nabla|ell)_\{[^}]+\}/g,
    wrapInInlineMath,
  );
  s = wrapSegmentMatch(s, /\\ell_(?:\{[^}]+\}|[0-9a-zA-Z+])/g, wrapInInlineMath);
  s = wrapSegmentMatch(
    s,
    /\\(?:boldsymbol|mathcal|mathbf|mathbb|mathrm)\{[^}]+\}(?:_\{[^}]+\}|_[0-9a-zA-Z+]+)*/g,
    wrapInInlineMath,
  );
  s = wrapSegmentMatch(
    s,
    /\\(?:mathbb|mathcal|mathrm|mathbf|boldsymbol)\{[^}]+\}(?:\[[^\]]*\])?/g,
    wrapInInlineMath,
  );
  s = wrapSegmentMatch(
    s,
    /\\(?:epsilon|varepsilon|gamma|alpha|beta|eta|theta|lambda|mu|sigma|pi|partial|nabla|ell)(?:_\{[^}]+\}|_[a-zA-Z0-9]+)?(?![a-zA-Z])/g,
    wrapInInlineMath,
  );
  s = wrapSegmentMatch(
    s,
    /\\[a-zA-Z]+(?:\{[^}]*\}|_\{[^}]+\}|_[a-zA-Z0-9])+/g,
    wrapInInlineMath,
  );

  // 简单函数式：p(θ|D)、N(0,σ^2I)
  s = wrapSegmentMatch(
    s,
    new RegExp(`\\b([A-Za-z])\\(([${UNICODE_GREEK}][^)]{0,40})\\)`, "g"),
    wrapInInlineMath,
  );

  return s;
}

function wrapProseSegment(segment: string): string {
  if (!segment.includes("$") || !/\\[a-zA-Z]+/.test(segment)) {
    return wrapProseSegmentInner(segment);
  }
  // 已有部分 $...$ 时，仅包裹其余裸 LaTeX 片段
  const parts = segment.split(/(\$(?!\$)[^$\n]+?\$(?!\$))/g);
  return parts
    .map((part, i) => (i % 2 === 1 ? part : wrapProseSegmentInner(part)))
    .join("");
}

function wrapProseLatex(content: string): string {
  const parts = content.split(/(\$\$[\s\S]+?\$\$|\$(?!\$)[^$\n]+?\$(?!\$))/g);
  return parts.map((part, i) => (i % 2 === 1 ? part : wrapProseSegment(part))).join("");
}

/** 独立成行的裸 LaTeX / Unicode 公式提升为 $$...$$ */
function wrapDisplayEquationLines(content: string): string {
  return content
    .split("\n")
    .map((line) => {
      if (line.includes("$")) return line;
      const trimmed = line.trim();
      if (!trimmed || /^[#>|*-]/.test(trimmed)) return line;
      if (/[\u4e00-\u9fff]/.test(trimmed)) return line;
      // 含 cases/aligned 的整行方程（如 Softmax 雅可比矩阵）
      if (
        /\\begin\{(?:cases|aligned|align)\}/.test(trimmed) &&
        /=/.test(trimmed) &&
        !/^=\s*\\begin/.test(trimmed)
      ) {
        const indent = line.match(/^(\s*)/)?.[1] ?? "";
        return `${indent}$$${trimmed}$$`;
      }
      if (line.includes("\\begin{")) return line;
      const hasFrac = /\\frac\{/.test(trimmed);
      const looksLikeEquation =
        /^[A-Za-z(\\]/.test(trimmed) &&
        /=/.test(trimmed) &&
        (trimmed.match(/\\[a-zA-Z]+/g) || []).length >= 1;
      const looksLikeUnicodeEquation =
        /=/.test(trimmed) &&
        UNICODE_MATH_RE.test(trimmed) &&
        /[_^∥‖]/.test(trimmed);
      if (!hasFrac && !looksLikeEquation && !looksLikeUnicodeEquation) return line;
      const indent = line.match(/^(\s*)/)?.[1] ?? "";
      return `${indent}$$${trimmed}$$`;
    })
    .join("\n");
}

/** 将「前缀 = $$\\begin{cases}...$$」合并为单个块级公式 */
function mergePrefixWithWrappedEnv(content: string): string {
  return content.replace(
    /([^\n$]+?)\s*=\s*\$\$(\\begin\{(?:cases|aligned|align)\}[\s\S]*?\\end\{(?:cases|aligned|align)\})\$\$/g,
    (_, prefix: string, envBlock: string) => `$$${prefix.trim()} = ${envBlock}$$`,
  );
}

/** 删除无对应 \\begin 的孤立 \\end{aligned|cases|align} 行 */
function removeOrphanEnvEnd(content: string): string {
  let result = content;
  for (const env of ["aligned", "cases", "align"] as const) {
    const beginCount = (result.match(new RegExp(`\\\\begin\\{${env}\\}`, "g")) || []).length;
    const endCount = (result.match(new RegExp(`\\\\end\\{${env}\\}`, "g")) || []).length;
    if (endCount <= beginCount) continue;
    let extra = endCount - beginCount;
    result = result.replace(
      new RegExp(`^\\s*(?:\\$\\s*)?\\\\end\\{${env}\\}(?:\\s*\\$)?\\s*$`, "gm"),
      (line) => (extra-- > 0 ? "" : line),
    );
  }
  return result;
}

/**
 * 包裹裸 LaTeX 环境块，并修复仅有尾部 $$ 的写法：
 *   \begin{cases}...\end{cases}$$
 */
function wrapBareLatexEnvironments(content: string): string {
  let result = content;
  const replacements: { start: number; end: number; text: string }[] = [];

  for (const env of DISPLAY_ENVS_LONGEST_FIRST) {
    const re = new RegExp(
      `\\\\begin\\{${env}\\}[\\s\\S]*?\\\\end\\{${env}\\}`,
      "g",
    );
    let match: RegExpExecArray | null;
    while ((match = re.exec(result)) !== null) {
      const blockStart = match.index;
      const blockEnd = blockStart + match[0].length;
      if (isAlreadyWrapped(result, blockStart, blockEnd)) continue;
      if (isInsideDisplayMath(result, blockStart)) continue;

      let consumeEnd = blockEnd;
      while (result.slice(consumeEnd, consumeEnd + 1) === "$") {
        consumeEnd++;
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
  return content.replace(INLINE_DOLLAR_RE, (match, inner: string) => {
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
  return content.replace(INLINE_DOLLAR_RE, (_, inner: string) =>
    processMathInner(inner, false),
  );
}

function processDisplayDollars(content: string): string {
  return replaceDisplayMathBlocks(content, (inner) => {
    let cleaned = inner.replace(/\s*\*{1,2}\s*$/, "").trim();
    const split = cleaned.match(
      /^([\s\S]+?\\mathbf\{[a-z]\}_[a-zA-Z])\s+(\\frac\{\\partial[\s\S]+)$/,
    );
    if (split) {
      cleaned = `${split[1].trim()}\n\n$$${split[2].trim()}$$`;
    }
    const repaired = repairEnvironmentClosures(cleaned);
    return stripDollarsInsideDisplay(repaired);
  });
}

function mergeDisplayLineWithCases(content: string): string {
  return content.replace(
    /\$\$([^$\n]*?=\s*)\n\s*(\\begin\{cases\})/g,
    (_, left: string, begin: string) => `$$${left}${begin}`,
  );
}

/** 按顺序配对 $$ 块级定界符（避免非贪婪正则误匹配下一行公式） */
function replaceDisplayMathBlocks(
  content: string,
  transform: (inner: string) => string,
): string {
  let result = "";
  let i = 0;
  while (i < content.length) {
    if (content[i] === "$" && content[i + 1] === "$") {
      const close = content.indexOf("$$", i + 2);
      if (close === -1) {
        result += content.slice(i);
        break;
      }
      const inner = content.slice(i + 2, close);
      result += `$$${transform(inner)}$$`;
      i = close + 2;
      continue;
    }
    result += content[i];
    i++;
  }
  return result;
}

/** 去掉块级公式内孤立的行内 $（如 \frac{$x_{i,k} - \mu_k}） */
function stripDollarsInsideDisplay(inner: string): string {
  let stripped = inner.replace(/\$([^$\n]*?)\$/g, "$1");
  stripped = stripped.replace(/(?<!\$)\$(?!\$)/g, "");
  return stripped.trim();
}

/** 去掉 display 环境内部的 $$ 定界符（aligned 内误写的 $$&\\propto...$$） */
function stripDollarsInsideEnvironments(content: string): string {
  let result = content;
  for (const env of DISPLAY_ENVS_LONGEST_FIRST) {
    const re = new RegExp(
      `\\\\begin\\{${env}\\}([\\s\\S]*?)\\\\end\\{${env}\\}`,
      "g",
    );
    result = result.replace(re, (_match, inner: string) => {
      let cleaned = inner.replace(/\$\$/g, "");
      cleaned = cleaned.replace(/\$([^$\n]*?)\$/g, "$1");
      cleaned = cleaned.replace(/(?<!\$)\$(?!\$)/g, "");
      return `\\begin{${env}}${cleaned}\\end{${env}}`;
    });
  }
  return result;
}

/** 将误写成块级的单 token 公式还原（如 $$\eta$$、$$\partial$$、$$z_k$$） */
function isErroneousDisplayToken(inner: string): boolean {
  const trimmed = inner.trim();
  if (!trimmed || trimmed.includes("=") || trimmed.includes("\\begin{")) return false;
  if (/^\\[a-zA-Z]+(\{[^}]*\}|_[a-zA-Z0-9{}]+)*$/.test(trimmed)) return true;
  if (/^[a-zA-Z_][a-zA-Z0-9_,^{}\\]*$/.test(trimmed)) return true;
  return false;
}

function flattenErroneousDisplayTokens(content: string): string {
  let result = content;
  let prev = "";
  while (prev !== result) {
    prev = result;
    result = result.replace(/\$\$\s*([^$\n]{1,80}?)\s*\$\$/g, (match, inner: string) =>
      isErroneousDisplayToken(inner) ? inner.trim() : match,
    );
  }
  return result;
}

function unwrapTokenDisplayMath(content: string): string {
  return flattenErroneousDisplayTokens(content);
}

/** 去掉 \\frac{}{} 内部的嵌套 $ / $$ 定界符 */
function stripDollarsInsideFrac(content: string): string {
  return content.replace(
    /\\frac\{(?:[^{}]|\{[^{}]*\})*\}\{(?:[^{}]|\{[^{}]*\})*\}/g,
    (frac) => {
      let s = frac;
      for (let i = 0; i < 4; i++) {
        const next = flattenErroneousDisplayTokens(
          s.replace(/\$([^$\n]+)\$/g, "$1"),
        );
        if (next === s) break;
        s = next;
      }
      return s;
    },
  );
}
/** 修复中文叙述里嵌套的 $$ / 碎裂 $（不处理已是 $$...$$ 的块） */
function repairProseDollarFragments(content: string): string {
  const parts = content.split(/(\$\$[\s\S]+?\$\$)/g);
  return parts.map((part, i) => {
    if (i % 2 === 1) return part;
    let s = part;
    s = s.replace(/\\pi\$\$\$?\\?sigma(\^2)?/g, "\\pi\\sigma$1");
    s = s.replace(/\\\|\$\$([^$]+?)\$\$\\\|/g, "\\|$1\\|");
    s = s.replace(/\$\\frac\{([^}]+)\}\$\{/g, "$\\frac{$1}{");
    s = s.replace(/(\d)\$\\sigma\$\^/g, "$1\\sigma^");
    s = s.replace(/\\eta\$\$\$?(\\lambda|\$\\lambda\$)/g, "\\eta\\lambda");
    s = s.replace(/\$\\eta\$\\lambda\$/g, "$\\eta\\lambda$");
    s = s.replace(/\)\^\{([^}]+)\}\$\}/g, ")^{$1}}");
    s = s.replace(/\}\$\}/g, "}}");
    s = s.replace(/\\\|\$([^$|]+)\$\|/g, "\\|$1\\|");
    s = s.replace(/(\d)\$\\sigma\$\^2/g, "$1\\sigma^2");
    return s;
  }).join("");
}

/** 修复嵌套/碎裂的 $ 定界符（模型或 wrapProse 误包裹导致） */
function repairFragmentedDelimiters(content: string): string {
  let result = flattenErroneousDisplayTokens(content);
  result = stripDollarsInsideFrac(result);

  // 先清理所有块级公式内的嵌套/孤立 $
  result = replaceDisplayMathBlocks(result, (inner) => {
    if (!/(?<!\$)\$(?!\$)/.test(inner)) return inner;
    return stripDollarsInsideDisplay(inner);
  });

  // 整段以 $$ 包裹且内含嵌套行内 $（如 mixup / batchnorm 粘连块）
  const trimmed = result.trim();
  if (
    trimmed.startsWith("$$") &&
    trimmed.endsWith("$$") &&
    (/\$[^$\n]+\$/.test(trimmed) || /(?<!\$)\$(?!\$)/.test(trimmed.slice(2, -2)))
  ) {
    const inner = stripDollarsInsideDisplay(trimmed.slice(2, -2));
    result = inner.includes("\n")
      ? `$$\n${inner}\n$$`
      : `$$${inner}$$`;
  }

  // 行内 $ 闭合后紧跟块级 $$（如 $\mathbf{x}_j$$）；排除含 = 的方程前缀
  result = result.replace(
    /(?<!\$)\$(\\[^$\n=]+|[a-zA-Z_][^=$\n]*)\$\$/g,
    (_, inner: string) => `${inner}$$`,
  );

  // $\cmd_{...}$^{m} / $\cmd_{...}$_{j} → \cmd_{...}^{m}
  result = result.replace(/\$([^$\n]+)\$(\^|_)/g, "$1$2");

  // 迭代展平嵌套 $...$
  for (let i = 0; i < 8; i++) {
    const next = result.replace(/\$([^$\n]+)\$/g, (match, inner: string) => {
      if (!inner.includes("$")) return match;
      return `$${inner.replace(/\$([^$\n]+)\$/g, "$1")}$`;
    });
    if (next === result) break;
    result = next;
  }

  // 块级公式内去掉残留的行内 / 孤立 $ 定界符
  result = replaceDisplayMathBlocks(result, (inner) => {
    if (!/(?<!\$)\$(?!\$)/.test(inner)) return inner;
    return stripDollarsInsideDisplay(inner);
  });

  // $$y_{i,k}$ = → $$y_{i,k} =
  result = result.replace(/\$\$([^$\n]+)\$\s*=/g, (_, inner: string) => `$$${inner} =`);

  // 粘连的多个块级公式拆开（仅同行且以 \\ 命令开头）
  result = result.replace(
    /\$\$([^\n\u4e00-\u9fff]{1,120}?)\$\$(\\(?:hat|frac|mathbf|mu|sigma|partial|tilde|[a-zA-Z]))/g,
    (_, inner: string, next: string) => `$$${inner}$$\n\n$$${next}`,
  );

  // 多个 $ / $$ 碎片组成的更新规则 → 单个 $$...$$
  result = result.replace(
    /(更新规则为：|梯度为：)\s*([\s\S]*?)(?=因子\s*\(|因子（|[\u4e00-\u9fff]{2,}[^\n]*[。；]|$)/,
    (match, prefix: string, body: string) => {
      if (!/\$/.test(body)) return match;
      const latex = body
        .replace(/\$\$([^$]+?)\$\$/g, "$1")
        .replace(/\$([^$\n]+)\$/g, "$1")
        .replace(/\$\$/g, "")
        .replace(/\s+/g, " ")
        .trim();
      if (!latex || latex.length < 3) return match;
      return `${prefix}$$\n${latex}\n$$`;
    },
  );

  // $\eta$$$$\lambda$ / $\eta$$ 等碎裂连写
  result = result.replace(
    /\$([^$\n]+)\$\${2,}\$([^$\n]+)\$/g,
    (_, a: string, b: string) => `$${a}${b}$`,
  );
  result = result.replace(
    /\(1\s*-\s*\$?\\?eta\s*\\?lambda\$\)/g,
    "(1 - $\\eta\\lambda$)",
  );
  result = result.replace(
    /每次减去\s*(?:\$?\\?eta\s*\\?lambda\$?|\\eta\s*\\lambda\$\$)/g,
    "每次减去 $\\eta\\lambda$",
  );
  result = result.replace(
    /因子\s*\(1\s*-\s*\$\\eta\$\s*\n?\s*\$\$\\lambda\$\)/g,
    "因子 (1 - $\\eta\\lambda$)",
  );

  // 块级公式内仍残留 $ 时，再次清理
  result = replaceDisplayMathBlocks(result, (inner) => {
    if (!/(?<!\$)\$(?!\$)/.test(inner)) return inner;
    return stripDollarsInsideDisplay(inner);
  });

  return result;
}

function normalizeMultilineDisplayMath(content: string): string {
  return replaceDisplayMathBlocks(content, (inner) => {
    if (!inner.includes("\n")) return inner;
    return `\n${inner.trim()}\n`;
  });
}

function normalizeLatexDelimiters(content: string): string {
  let result = content;
  result = result.replace(/\\\[([\s\S]*?)\\\]/g, (_, inner: string) => `$$${inner.trim()}$$`);
  result = result.replace(/\\\(([\s\S]*?)\\\)/g, (_, inner: string) => `$${inner.trim()}$`);
  return result;
}

function trimOrphanTrailingDollars(content: string): string {
  // 仅去掉中文标点后多余的孤立 $（如 「参数。$」），勿误伤行尾正常的 $...$ 闭合
  return content.replace(/([\u4e00-\u9fff。])\$(\s*)$/gm, (_, before: string, tail: string) => before + tail);
}

/**
 * 对 Markdown 文本中的数学片段做预处理。
 */
export function preprocessMathContent(content: string): string {
  let result = normalizeLatexDelimiters(content);
  result = removeCorruptMashedDisplayPrefix(result);
  result = dedupeAdjacentPhrases(result);
  result = separateGluedMarkdown(result);
  result = repairUnclosedDisplayBlocks(result);
  result = fixMalformedSubscripts(result);
  result = fixEnvRowSeparators(result);
  result = stripDollarsInsideEnvironments(result);
  result = normalizeDollarRuns(result);
  result = unwrapTokenDisplayMath(result);
  result = mergeSplitDisplayMath(result);
  result = mergeDisplayLineWithCases(result);
  result = dedupeConsecutiveAlignedBegin(result);
  result = fixOrphanAlignedEnd(result);
  result = wrapDisplayEquationLines(result);

  if (!containsLatex(result)) {
    return wrapProseLatex(result);
  }

  result = normalizeDollarRuns(result);
  result = stripDollarsInsideEnvironments(result);
  result = unwrapTokenDisplayMath(result);
  result = wrapBareLatexEnvironments(result);
  result = mergePrefixWithWrappedEnv(result);
  result = collapseMultilineInlineMath(result);
  result = processDisplayDollars(result);
  result = processInlineDollars(result);
  result = normalizeDollarRuns(result);
  result = closeUnclosedDollarDelimiters(result);
  result = repairFragmentedDelimiters(result);
  result = normalizeMultilineDisplayMath(result);
  result = repairProseDollarFragments(result);
  result = wrapProseLatex(result);
  result = repairFragmentedDelimiters(result);
  result = repairProseDollarFragments(result);
  result = wrapProseLatex(result);
  result = repairProseDollarFragments(result);
  result = removeOrphanEnvEnd(result);
  result = stripLeadingCorruptDisplayBlocks(result);
  result = trimOrphanTrailingDollars(result);

  return result;
}
