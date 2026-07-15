import { preprocessMathContent } from "./preprocessMath";

const cases = [
  {
    name: "bare cases",
    input:
      "=\\begin{cases} \\hat{y}_k (1 - \\hat{y}_k), & m = k \\\\ -\\hat{y}_m \\hat{y}_k, & m \\neq k \\end{cases}",
    expectIncludes: ["$$\\begin{cases}", "\\end{cases}$$"],
    expectNotIncludes: ["$$$$"],
  },
  {
    name: "aligned with triple dollar",
    input:
      "代入得：\\begin{aligned} \\frac{\\partial \\ell}{\\partial z_k} &= -y_k \\\\ \\end{aligned}$$$\\square",
    expectIncludes: ["$$\\begin{aligned}", "\\end{aligned}$$", "\\square"],
    expectNotIncludes: ["$$$", "$$$$"],
  },
  {
    name: "malformed subscripts",
    input: "时，\\sum{m \\neq k} y_m 和 \\lambda{\\max}(\\mathbf{H})",
    expectIncludes: ["\\sum_{m \\neq k}", "\\lambda_{\\max}", "$\\mathbf{H}$"],
  },
  {
    name: "malformed boldsymbol subscript",
    input: "\\boldsymbol{\\theta}{t+1} = \\boldsymbol{\\theta}_t",
    expectIncludes: ["\\boldsymbol{\\theta}_{t+1}", "\\boldsymbol{\\theta}_t"],
  },
  {
    name: "hat y k without underscore",
    input: "(1 - \\hat{y}k)",
    expectIncludes: ["\\hat{y}_k"],
  },
  {
    name: "duplicate phrase",
    input: "代入得：代入得：\\begin{aligned} a &= b \\end{aligned}",
    expectIncludes: ["代入得：$$\\begin{aligned}"],
    expectNotIncludes: ["代入得：代入得：", "$$$$"],
  },
  {
    name: "display math not broken by inline pass",
    input: "$$\\begin{aligned} a &= b \\end{aligned}$$",
    expectIncludes: ["$$\\begin{aligned} a &= b \\end{aligned}$$"],
    expectNotIncludes: ["$$$$"],
  },
  {
    name: "merge partial display with cases",
    input:
      "$$\\partial |\\theta_j| =$$\\begin{cases}\n\\{-1\\}, & \\theta_j < 0 \\\\\n\\{1\\}, & \\theta_j > 0\n\\end{cases}$$",
    expectIncludes: ["\\partial |\\theta_j| = \\begin{cases}", "\\end{cases}"],
    expectNotIncludes: ["=$$\\begin", "$$$$"],
  },
  {
    name: "merge dropout cases",
    input: "$$h_j' = \n$$\\begin{cases}\n0, & p \\\\\nh_j, & 1-p\n\\end{cases}$$",
    expectIncludes: ["h_j' = \\begin{cases}", "\\end{cases}"],
    expectNotIncludes: ["=$$\\begin"],
  },
  {
    name: "orphan end aligned",
    input:
      "取负对数：\n\n-\\log p(\\boldsymbol{\\theta} \\mid \\mathcal{D}) &= a \\\\\n&\\propto L_0 \\\\\n\\end{aligned}$$",
    expectIncludes: ["\\begin{aligned}", "-\\log p", "\\end{aligned}"],
  },
  {
    name: "wrap prose L0",
    input: "在原始损失函数 L_0(\\theta) 的基础上",
    expectIncludes: ["$L_0(\\theta)$"],
  },
  {
    name: "wrap prose boldsymbol",
    input: "参数 \\boldsymbol{\\theta} 服从先验",
    expectIncludes: ["$\\boldsymbol{\\theta}$"],
  },
  {
    name: "inline dollar merge with cases",
    input: "$\\partial |\\theta_j| =$$\\begin{cases}\na \\\\\nb\n\\end{cases}$$",
    expectIncludes: ["\\partial |\\theta_j| = \\begin{cases}"],
    expectNotIncludes: ["=$$\\begin"],
  },
  {
    name: "display equation line",
    input: "L(\\theta)=L_0(\\theta)+ \\frac{\\lambda}{2} \\|\\theta\\|_2^2",
    expectIncludes: ["$$L(\\theta)=L_0(\\theta)+ \\frac{\\lambda}{2}"],
  },
  {
    name: "ell subscript in prose",
    input: "参数 \\theta 的 \\ell_2 范数",
    expectIncludes: ["$\\ell_2$"],
  },
  {
    name: "sum not broken by subscript pass",
    input: "时，\\sum_{m \\neq k} y_m",
    expectIncludes: ["$\\sum_{m \\neq k}$", "$y_m$"],
    expectNotIncludes: ["$\\$sum", "$y_m$$", "$sum_"],
  },
  {
    name: "unicode L0 theta",
    input: "在原始损失函数 L_0(θ) 的基础上",
    expectIncludes: ["$L_0(θ)$"],
  },
  {
    name: "unicode theta MAP",
    input: "θ_MAP = argmax_θ p(θ|D)",
    expectIncludes: ["θ_MAP", "argmax_θ", "p(θ|D)"],
    expectNotIncludes: ["θ\n", "_MAP\n"],
  },
  {
    name: "unicode ell subscript",
    input: "参数 θ 的 ℓ_2 范数",
    expectIncludes: ["$ℓ_2$"],
  },
  {
    name: "unicode norm subscript",
    input: "惩罚项 ∥θ∥_2^2 与 λ>0",
    expectIncludes: ["$∥θ∥_2$"],
  },
  {
    name: "unicode display equation line",
    input: "L(θ)=L_0(θ)+λ/2∥θ∥_2^2",
    expectIncludes: ["$$L(θ)=L_0(θ)+λ/2∥θ∥_2^2$$"],
  },
  {
    name: "orphan aligned full proof",
    input:
      "证明：取负对数：\n\n-\\log p(\\boldsymbol{\\theta} \\mid \\mathcal{D}) &= -\\log p(\\mathcal{D} \\mid \\boldsymbol{\\theta}) - \\log p(\\boldsymbol{\\theta}) + \\text{const} \\\\\n&\\propto L_0(\\boldsymbol{\\theta}) + \\frac{1}{2\\sigma^2} \\|\\boldsymbol{\\theta}\\|_2^2\n\\end{aligned}$$",
    expectIncludes: ["\\begin{aligned}", "\\end{aligned}", "-\\log p"],
  },
  {
    name: "glued bold after cases",
    input: "\\end{cases}$$**笔记**：L1 正则化",
    expectIncludes: ["\\end{cases}$$\n\n**笔记**"],
  },
  {
    name: "glued chinese after cases",
    input: "\\end{cases}$$实践中常用符号函数",
    expectIncludes: ["\\end{cases}$$\n\n实践中"],
  },
  {
    name: "L1 cases glued to prose",
    input:
      "$$\\partial |\\theta_j| =$$\\begin{cases}\n\\{-1\\}, & \\theta_j < 0 \\\\\n\\{1\\}, & \\theta_j > 0\n\\end{cases}$$实践中常用",
    expectIncludes: ["\\partial |\\theta_j| = \\begin{cases}", "\n\n实践中"],
    expectNotIncludes: ["\\end{cases}$$实践中"],
  },
  {
    name: "unicode subscript digit",
    input: "损失 L₀(θ) 与 L₁(θ)",
    expectIncludes: ["$L₀$", "$L₁$"],
  },
  {
    name: "mixup nested display dollars",
    input: String.raw`$$\tilde{$\mathbf{x}$} = \lambda $\mathbf{x}_i$ + (1-\lambda) $\mathbf{x}_j$, \quad \tilde{y} = \lambda $y_i$ + (1-\lambda) $y_j$$$`,
    expectIncludes: ["$$\\tilde{\\mathbf{x}}", "y_j$$"],
    expectNotIncludes: ["$\\mathbf{x}$", "$y_i$", "$$$"],
  },
  {
    name: "triple dollar closes display block",
    input: "$$a + b$$$",
    expectIncludes: ["$$a + b$$"],
    expectNotIncludes: ["$$$"],
  },
  {
    name: "mixup with wrapped lambda and glued 其中",
    input: String.raw`$$\tilde{$\mathbf{x}$} = $\lambda$ $\mathbf{x}_i$ + (1-$\lambda$) $\mathbf{x}_j$, \quad $\tilde{y}$ = $\lambda$ $y_i$ + (1-$\lambda$) $y_j$$$其中 \lambda \sim \text{Beta}(\alpha, \alpha)`,
    expectIncludes: ["$$\\tilde{\\mathbf{x}}", "y_j$$", "\n\n其中"],
    expectNotIncludes: ["$$$", "$\\mathbf{x}$", "$$\\lambda$$"],
  },
  {
    name: "label smoothing triple dollar glued 其中",
    input: String.raw`$$$y_k$^{$\text{LS}$} = (1 - $\alpha$) $y_k$ + $\frac{$\alpha$}{K}$$其中 K 为类别数`,
    expectIncludes: ["$$y_k^{\\text{LS}}", "K}$$", "\n\n其中"],
    expectNotIncludes: ["$$$", "$\\alpha$"],
  },
  {
    name: "aligned proof with gaussian prose",
    input: String.raw`\begin{aligned}
-\log p(\boldsymbol{\theta} \mid \mathcal{D}) &= a \\
$$&\propto $L_0(\boldsymbol{\theta})$ + $\frac{1}{2\sigma^2}$ \|$\boldsymbol{\theta}\|_2^2$$
\end{aligned}
$$其中 p($\boldsymbol{\theta}$) = $\frac{1}{(2\pi$$\sigma$^2)^{p/2}$} \exp\left(-\frac{\|$$\boldsymbol{\theta}$$\|_2^2}{2\sigma^2}\right)`,
    expectIncludes: ["\\begin{aligned}", "&\\propto L_0", "\\end{aligned}", "$$", "(2\\pi\\sigma^2)"],
    expectNotIncludes: ["$$&\\propto", "\\pi$$", "$$其中", "\\begin{aligned}\n\\begin{aligned}"],
  },
  {
    name: "no duplicate begin aligned when already present",
    input: String.raw`\begin{aligned}
-\log p(\boldsymbol{\theta} \mid \mathcal{D}) &= -\log p(\mathcal{D} \mid \boldsymbol{\theta}) - \log p(\boldsymbol{\theta}) + \text{const} \\
&\propto L_0(\boldsymbol{\theta}) + \frac{1}{2\sigma^2} \|\boldsymbol{\theta}\|_2^2
\end{aligned}`,
    expectIncludes: ["\\begin{aligned}", "\\end{aligned}", "&\\propto L_0"],
    expectNotIncludes: ["\\begin{aligned}\n\\begin{aligned}"],
  },
  {
    name: "dedupe model double begin aligned",
    input: String.raw`\begin{aligned}
\begin{aligned}
-\log p(\boldsymbol{\theta} \mid \mathcal{D}) &= a \\
\end{aligned}`,
    expectIncludes: ["\\begin{aligned}", "&= a"],
    expectNotIncludes: ["\\begin{aligned}\n\\begin{aligned}"],
  },
  {
    name: "softmax jacobian cases on one line",
    input: String.raw`Softmax 的雅可比矩阵为：
\frac{\partial \hat{y}_m}{\partial z_k} = \begin{cases} \hat{y}_k (1 - \hat{y}_k), & m = k \\ -\hat{y}_m \hat{y}_k, & m \neq k \end{cases}`,
    expectIncludes: ["$$\\frac{\\partial \\hat{y}_m}{\\partial z_k}", "\\begin{cases}", "\\end{cases}$$"],
    expectNotIncludes: ["$\\partial$", "$$\\partial$$", "$\\frac{$"],
  },
  {
    name: "softmax aligned proof with duplicate 代入得",
    input: String.raw`代入得：
代入得：
\begin{aligned} \frac{\partial \ell}{\partial z_k} &= -\frac{y_k}{\hat{y}_k} \cdot \hat{y}_k (1 - \hat{y}k) - \sum{m \neq k} \frac{y_m}{\hat{y}_m} \cdot (-\hat{y}_m \hat{y}_k) \\ &= \hat{y}_k - y_k \end{aligned}`,
    expectIncludes: ["代入得：", "$$\\begin{aligned}", "\\hat{y}_k", "\\sum_{m \\neq k}", "\\end{aligned}$$"],
    expectNotIncludes: ["代入得：\n代入得：", "\\hat{y}k", "\\sum{m"],
  },
  {
    name: "orphan end aligned line removed",
    input: String.raw`\end{aligned}


$\square$`,
    expectIncludes: ["$\\square$"],
    expectNotIncludes: ["\\end{aligned}"],
  },
  {
    name: "corrupt mashed display prefix removed",
    input: String.raw`$$ \nabla_{\mathbf{w}} L_{\text{MSE}} = \frac{2}{N} \sum_{i=1}^{N} (\hat{y}i - y_i) \mathbf{x}i \frac{\partial L{\text{MSE}}}{\partial b} = \frac{2}{N} \sum{i=1}^{N} (\hat{y}_i - y_i) **


令 $r_i = \hat{y}_i - y_i$`,
    expectIncludes: ["令 $r_i = \\hat{y}_i"],
    expectNotIncludes: ["\\nabla_{\\mathbf{w}}", "**", "L{\\text{MSE}}"],
  },
  {
    name: "corrupt closed display block at start removed",
    input: String.raw`$$ \nabla_{\mathbf{w}} L_{\text{MSE}} = \frac{2}{N} \sum (\hat{y}_i - y_i) \mathbf{x}_i \frac{\partial L_{\text{MSE}}}{\partial b} = \frac{2}{N} \sum (\hat{y}_i - y_i) $$

令 $r_i$`,
    expectIncludes: ["令 $r_i$"],
    expectNotIncludes: ["\\nabla_{\\mathbf{w}}"],
  },
  {
    name: "cases single backslash row separator",
    input: String.raw`\frac{\partial \hat{y}_m}{\partial z_k} = \begin{cases} \hat{y}_k (1 - \hat{y}_k), & m = k \ -\hat{y}_m \hat{y}_k, & m \neq k \end{cases}`,
    expectIncludes: ["m = k \\\\ -\\hat{y}_m"],
    expectNotIncludes: ["m = k \\ -"],
  },
  {
    name: "L text MSE subscript fix",
    input: String.raw`$\frac{\partial L{\text{MSE}}}{\partial b}$`,
    expectIncludes: ["L_{\\text{MSE}}"],
    expectNotIncludes: ["L{\\text{MSE}}"],
  },
  {
    name: "hat mathbf y order fix",
    input: String.raw`设 $\hat_{\mathbf{y}} = \text{softmax}(\mathbf{z})$`,
    expectIncludes: ["\\hat{\\mathbf{y}}"],
    expectNotIncludes: ["\\hat_{\\mathbf{y}}"],
  },
  {
    name: "aligned single backslash row separator",
    input: String.raw`\begin{aligned} a &= b \ &= c \end{aligned}`,
    expectIncludes: ["b \\\\ &= c"],
    expectNotIncludes: ["b \\ &= c"],
  },
  {
    name: "frac with erroneous display tokens",
    input: String.raw`\frac{$$\partial$$ $$\ell$$}{$$\partial$$ $$z_k$$}`,
    expectIncludes: ["$\\frac{\\partial \\ell}{\\partial z_k}$"],
    expectNotIncludes: ["$$\\partial$$", "$$z_k$$", "$\\partial$"],
  },
  {
    name: "theorem nested text subscript",
    input: "**陈述**：L_{\\text{MSE}} 在 $\\theta=0$ 处取极小",
    expectIncludes: ["$L_{\\text{MSE}}$"],
  },
  {
    name: "theorem norm inequality",
    input: String.raw`\|\nabla L(\theta)\|^2 \geq 2\mu L(\theta)`,
    expectIncludes: [String.raw`$\|\nabla L(\theta)\|^2$`],
    expectNotIncludes: ["|$\\nabla$"],
  },
  {
    name: "theorem section labels preserved",
    input: String.raw`**证明**：
$$\nabla L(\theta) = 0$$`,
    expectIncludes: ["**证明**", String.raw`$$\nabla L(\theta) = 0$$`],
  },
];

let failed = 0;
/** remark-math 需要 $$\n...\n$$；断言时忽略换行差异 */
function compactDisplayDollars(s: string): string {
  return s.replace(/\$\$\r?\n([\s\S]*?)\r?\n\$\$/g, (_, inner: string) => `$$${inner}$$`);
}

for (const c of cases) {
  const out = preprocessMathContent(c.input);
  const compact = compactDisplayDollars(out);
  const ok =
    c.expectIncludes.every((s) => out.includes(s) || compact.includes(s)) &&
    (c.expectNotIncludes?.every((s) => !out.includes(s) && !compact.includes(s)) ?? true);
  if (!ok) {
    failed++;
    console.error(`FAIL ${c.name}`);
    console.error("  in:", c.input.slice(0, 100));
    console.error("  out:", out.slice(0, 150));
  } else {
    console.log(`OK ${c.name}`);
  }
}
process.exit(failed > 0 ? 1 : 0);
