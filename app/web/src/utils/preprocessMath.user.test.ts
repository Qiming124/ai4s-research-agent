import { preprocessMathContent } from "./preprocessMath";

const samples: {
  name: string;
  input: string;
  mustNotInclude?: string[];
  expectIncludes?: string[];
}[] = [
  {
    name: "cases glued update rule",
    input: String.raw`\begin{cases}
\{-1\}, & \theta_j < 0 \\
[-1, 1], & \theta_j = 0 \\
\{1\}, & \theta_j > 0
\end{cases}$$实践中常用符号函数近似：$\frac{\partial |\theta_j|}{\partial \theta_j} \approx \text{sign}(\theta_j)$（在 $\theta_j = 0$ 时常取 0）。更新规则为：$$$\theta_{j, t+1}$ = $\theta_{j, t}$ - \eta \left( $\nabla_{\theta_j}$ $L_0($\boldsymbol{\theta}_t$)$ + \lambda \cdot \text{sign}($\theta_{j,t}$) \right)$$`,
    mustNotInclude: ["$$$", "$\\sum", "$L_0($", "$\\boldsymbol"],
  },
  {
    name: "batchnorm mashed",
    input: String.raw`$$\mu_k = \frac{1}{m} $\sum_{i=1}$^{m} $x_{i,k}$, \quad \sigma_k^2 = \frac{1}{m} $\sum_{i=1}$^{m} ($x_{i,k}$ - \mu_k)^2$$\hat{x}_{i,k} = \frac{x_{i,k} - \mu_k}{\sqrt{\sigma_k^2 + \epsilon}}$$y_{i,k}$ = \gamma_k \hat{x}_{i,k} + \beta_k$$`,
    mustNotInclude: ["$\\sum_{i=1}$", "$x_{i,k}$", "$$y_{i,k}$"],
  },
  {
    name: "mixup nested",
    input: String.raw`$$\tilde{$\mathbf{x}$} = \lambda $\mathbf{x}_i$ + (1-\lambda) $\mathbf{x}_j$, \quad \tilde{y} = \lambda $y_i$ + (1-\lambda) $y_j$$$`,
    mustNotInclude: ["$\\mathbf{x}$", "$y_i$", "$\\mathbf{x}_i$"],
    expectIncludes: ["$$\\tilde{\\mathbf{x}}"],
  },
  {
    name: "dropout split line",
    input: String.raw`$$h_j' = 
\begin{cases}
0, & \text{以概率 } p \\
\frac{h_j}{1-p}, & \text{以概率 } 1-p
\end{cases}$$`,
    mustNotInclude: ["=$$\\begin", "$$h_j' = \n\n$$"],
  },
  {
    name: "label smoothing",
    input: String.raw`$$$y_k$^{\text{LS}} = (1 - \alpha) $y_k$ + \frac{\alpha}{K}$$`,
    mustNotInclude: ["$$$", "$y_k$"],
  },
  {
    name: "dropout inline cases prefix",
    input: String.raw`$h_j' = \begin{cases} 0, & \text{以概率 } p \ \frac{h_j}{1-p}, & \text{以概率 } 1-p \end{cases}`,
    mustNotInclude: ["$h_j' = $$\\begin", "$$\\begin{cases}"],
    expectIncludes: ["$$h_j' = \\begin{cases}"],
  },
  {
    name: "batchnorm hat x orphan dollar",
    input: String.raw`$$\hat{x}_{i,k} = \frac{$x_{i,k} - \mu_k}{\sqrt{\sigma_k^2 + \epsilon}}$$`,
    mustNotInclude: ["$x_{i,k}$", "$$\\n\\n$$"],
    expectIncludes: ["\\frac{x_{i,k} - \\mu_k}"],
  },
  {
    name: "batchnorm prose epsilon gamma",
    input: String.raw`$$y_{i,k} = \gamma_k \hat{x}_{i,k} + \beta_k$$
其中 \epsilon > 0 为防止除零的小常数，\gamma_k 和 \beta_k 为可学习的缩放和平移参数。`,
    expectIncludes: ["$\\epsilon > 0$", "$\\gamma_k$", "$\\beta_k$"],
  },
  {
    name: "gradient doc corrupt prefix and softmax proof",
    input: String.raw`$$ \nabla_{\mathbf{w}} L_{\text{MSE}} = \frac{2}{N} \sum_{i=1}^{N} (\hat{y}i - y_i) \mathbf{x}i \frac{\partial L{\text{MSE}}}{\partial b} = \frac{2}{N} \sum{i=1}^{N} (\hat{y}_i - y_i) **


令 $r_i = \hat{y}_i - y_i$。

其中 $\frac{\partial \ell}{\partial \hat{y}_m} = -\frac{y_m}{\hat{y}_m}$。Softmax 的雅可比矩阵为：
\frac{\partial \hat{y}_m}{\partial z_k} = \begin{cases} \hat{y}_k (1 - \hat{y}_k), & m = k \ -\hat{y}_m \hat{y}_k, & m \neq k \end{cases}

代入得：
代入得：
\begin{aligned} \frac{\partial \ell}{\partial z_k} &= a \ &= b \end{aligned}`,
    expectIncludes: ["令 $r_i =", "\\begin{cases}", "\\\\ &= b", "代入得："],
    mustNotInclude: [
      "$$ \\nabla",
      "代入得：\n代入得：",
      "m = k \\ -",
      " \\ &= b",
    ],
  },
];

let failed = 0;
for (const s of samples) {
  const out = preprocessMathContent(s.input);
  const bad = (s.mustNotInclude ?? []).filter((x) => out.includes(x));
  const missing = (s.expectIncludes ?? []).filter((x) => !out.includes(x));
  if (bad.length > 0 || missing.length > 0) {
    failed++;
    console.error(`FAIL ${s.name}`);
    if (bad.length) console.error("  still has:", bad);
    if (missing.length) console.error("  missing:", missing);
    console.error("  out:", out.slice(0, 300));
  } else {
    console.log(`OK ${s.name}`);
  }
}
process.exit(failed > 0 ? 1 : 0);
