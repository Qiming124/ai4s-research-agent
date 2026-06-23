import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeKatex from "rehype-katex";
import { visit } from "unist-util-visit";
import type { Element, Root } from "hast";
import { preprocessMathContent } from "./preprocessMath";

async function renderToHast(markdown: string): Promise<Root> {
  const processed = preprocessMathContent(markdown);
  const processor = unified()
    .use(remarkParse)
    .use(remarkMath)
    .use(remarkGfm)
    .use(remarkRehype)
    .use(rehypeKatex, { strict: "ignore", errorColor: "#b45309" });

  const tree = processor.parse(processed);
  return processor.run(tree) as Promise<Root>;
}

function countKatexErrors(tree: Root): number {
  let count = 0;
  visit(tree, "element", (node: Element) => {
    const cls = node.properties?.className;
    if (Array.isArray(cls) && cls.some((c) => String(c).includes("katex-error"))) {
      count++;
    }
  });
  return count;
}

/** GFM 将裸 _ 解析为 <em> 单字符斜体 */
function countBrokenEmphasis(tree: Root): number {
  let count = 0;
  visit(tree, "element", (node: Element) => {
    if (node.tagName !== "em") return;
    const text = node.children
      .filter((c) => c.type === "text")
      .map((c) => (c.type === "text" ? c.value : ""))
      .join("");
    if (text.length === 1 && /[0-9A-Za-z]/.test(text)) {
      count++;
    }
  });
  return count;
}

const renderCases = [
  {
    name: "unicode L0 in prose",
    input: "在原始损失函数 L_0(θ) 的基础上",
  },
  {
    name: "merged L1 cases",
    input:
      "$$\\partial |\\theta_j| =$$\\begin{cases}\n\\{-1\\}, & \\theta_j < 0 \\\\\n\\{1\\}, & \\theta_j > 0\n\\end{cases}$$",
  },
  {
    name: "orphan aligned proof",
    input:
      "-\\log p(\\boldsymbol{\\theta} \\mid \\mathcal{D}) &= a \\\\\n&\\propto L_0(\\boldsymbol{\\theta}) \\\\\n\\end{aligned}$$",
  },
  {
    name: "display equation line",
    input: "L(\\theta)=L_0(\\theta)+ \\frac{\\lambda}{2} \\|\\theta\\|_2^2",
  },
  {
    name: "malformed subscripts",
    input: "时，\\sum{m \\neq k} y_m 和 \\lambda{\\max}(\\mathbf{H})",
  },
  {
    name: "dropout cases display",
    input: String.raw`$h_j' = \begin{cases} 0, & \text{以概率 } p \ \frac{h_j}{1-p}, & \text{以概率 } 1-p \end{cases}`,
  },
  {
    name: "batchnorm hat x nested dollar",
    input: String.raw`$$\hat{x}_{i,k} = \frac{$x_{i,k} - \mu_k}{\sqrt{\sigma_k^2 + \epsilon}}$$`,
  },
  {
    name: "gradient doc full",
    input: String.raw`$$ \nabla_{\mathbf{w}} L_{\text{MSE}} = \frac{2}{N} \sum_{i=1}^{N} (\hat{y}i - y_i) \mathbf{x}i \frac{\partial L{\text{MSE}}}{\partial b} = \frac{2}{N} \sum{i=1}^{N} (\hat{y}_i - y_i) **


令 $r_i = \hat{y}_i - y_i$。

\frac{\partial \hat{y}_m}{\partial z_k} = \begin{cases} \hat{y}_k (1 - \hat{y}_k), & m = k \ -\hat{y}_m \hat{y}_k, & m \neq k \end{cases}

\begin{aligned} a &= b \ &= c \end{aligned}`,
  },
  {
    name: "frac display tokens inside partial",
    input: String.raw`\frac{$$\partial$$ $$\ell$$}{$$\partial$$ $$z_k$$}`,
  },
];

let failed = 0;
for (const c of renderCases) {
  const tree = await renderToHast(c.input);
  const errors = countKatexErrors(tree);
  const brokenEm = countBrokenEmphasis(tree);
  if (errors > 0 || brokenEm > 0) {
    failed++;
    console.error(`FAIL render ${c.name}: katex-error=${errors}, broken-em=${brokenEm}`);
  } else {
    console.log(`OK render ${c.name}`);
  }
}

process.exit(failed > 0 ? 1 : 0);
