"""preprocessMath 单元测试（纯逻辑，不依赖 DOM）。"""

from __future__ import annotations

import subprocess
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

PREPROCESS_JS = r"""
const DISPLAY_ENVS = ['cases','align','aligned','alignat','gather','multline','matrix','pmatrix','bmatrix','vmatrix','Vmatrix','equation','split','array'];

function containsDisplayEnv(latex) {
  return DISPLAY_ENVS.some(env => latex.includes(`\\begin{${env}}`));
}
function repairEnvironmentClosures(latex) {
  let result = latex;
  for (const env of DISPLAY_ENVS) {
    const begin = `\\begin{${env}}`;
    const end = `\\end{${env}}`;
    if (!result.includes(begin) || result.includes(end)) continue;
    result = result.trimEnd();
    if (result.endsWith('&')) result += ' \\cdots';
    result += ` \\end{${env}}`;
  }
  return result;
}
function processMathInner(latex, forceDisplay) {
  const repaired = repairEnvironmentClosures(latex.trim());
  if (forceDisplay || containsDisplayEnv(repaired)) return `$$${repaired}$$`;
  return `$${repaired}$`;
}
function isAlreadyWrapped(content, start, end) {
  const before2 = content.slice(Math.max(0, start - 2), start);
  if (before2 === '$$') return true;
  const before1 = content.slice(Math.max(0, start - 1), start);
  const after1 = content.slice(end, end + 1);
  if (before1 === '$' && before2 !== '$$' && after1 === '$') {
    const after2 = content.slice(end, end + 2);
    if (after2 !== '$$') return true;
  }
  return false;
}
function wrapBareLatexEnvironments(content) {
  let result = content;
  const replacements = [];
  for (const env of DISPLAY_ENVS) {
    const re = new RegExp(`\\\\begin\\{${env}\\}[\\s\\S]*?\\\\end\\{${env}\\}`, 'g');
    let match;
    while ((match = re.exec(result)) !== null) {
      const blockStart = match.index;
      const blockEnd = blockStart + match[0].length;
      if (isAlreadyWrapped(result, blockStart, blockEnd)) continue;
      let consumeEnd = blockEnd;
      if (result.slice(blockEnd, blockEnd + 2) === '$$') consumeEnd = blockEnd + 2;
      else if (result.slice(blockEnd, blockEnd + 1) === '$') consumeEnd = blockEnd + 1;
      replacements.push({ start: blockStart, end: consumeEnd, text: `$$${match[0]}$$` });
    }
  }
  replacements.sort((a, b) => b.start - a.start);
  for (const { start, end, text } of replacements) {
    result = result.slice(0, start) + text + result.slice(end);
  }
  return result;
}
function collapseMultilineInlineMath(content) {
  return content.replace(/\$(?!\$)([\s\S]*?)\$(?!\$)/g, (match, inner) => {
    if (!inner.includes('\n')) return match;
    const collapsed = inner.replace(/\s*\n+\s*/g, ' ').trim();
    return processMathInner(collapsed, containsDisplayEnv(collapsed));
  });
}
function closeUnclosedDollarDelimiters(content) {
  let count = 0;
  for (let i = 0; i < content.length; i++) {
    if (content[i] === '$' && (i === 0 || content[i - 1] !== '\\')) count++;
  }
  return count % 2 === 1 ? content + '$' : content;
}
function processInlineDollars(content) {
  return content.replace(/\$([^$\n]+?)\$/g, (_, inner) => processMathInner(inner, false));
}
function processDisplayDollars(content) {
  return content.replace(/\$\$([\s\S]*?)\$\$/g, (_, inner) => processMathInner(inner, true));
}
function preprocessMathContent(content) {
  if (!content.includes('$') && !content.includes('\\begin{')) return content;
  let result = content;
  result = wrapBareLatexEnvironments(result);
  result = collapseMultilineInlineMath(result);
  result = processDisplayDollars(result);
  result = processInlineDollars(result);
  result = closeUnclosedDollarDelimiters(result);
  if (result !== content) result = processInlineDollars(result);
  return result;
}

const cases = [
  ['promote inline cases', '$\\begin{cases} a & b \\\\ c & d \\end{cases}$', (o) => o.startsWith('$$')],
  ['repair incomplete', '$\\begin{cases} \\frac{1}{2}(y-\\hat{y})^2, &', (o) => o.includes('\\end{cases}')],
  ['bare cases trailing $$', 'Huber\\n\\begin{cases}a\\\\b\\end{cases}$$', (o) => o.includes('$$\\begin{cases}') && o.endsWith('$$')],
  ['multiline inline', '$L\n: Y \\times Y \\to \\mathbb{R}$', (o) => o.includes('L : Y')],
  ['subscript preserved', '$L_{\\text{MSE}}(y, \\hat{y})$', (o) => o.includes('L_{\\text{MSE}}')],
];

let failed = 0;
for (const [name, input, check] of cases) {
  const out = preprocessMathContent(input);
  if (!check(out)) { console.error('FAIL', name, JSON.stringify(out)); failed++; }
  else console.log('OK', name);
}
process.exit(failed);
"""


def test_preprocess_math_via_node() -> None:
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", PREPROCESS_JS],
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
