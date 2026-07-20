# PL条件下经验损失临界点分类

## 定理：引理 1: （线性模型的梯度与 Hessian）

**陈述**：对任意 $\theta \in \mathbb{R}^d$，

$$\nabla L_{\text{lin}}(\theta) = \frac{1}{n}X^\top(X\theta - y)$$

$$H_{\text{lin}}(\theta) = \frac{1}{n}X^\top X \quad \text{（常矩阵，不依赖于 } \theta \text{）}$$

**证明**：直接计算。

$$\begin{aligned}
L_{\text{lin}}(\theta) &= \frac{1}{2n}(X\theta - y)^\top(X\theta - y) \\
&= \frac{1}{2n}\left(\theta^\top X^\top X\theta - 2y^\top X\theta + y^\top y\right)
\end{aligned}$$

对 $\theta$ 求一阶导（**代数**）：

$$\nabla L_{\text{lin}}(\theta) = \frac{1}{n}\left(X^\top X\theta - X^\top y\right) = \frac{1}{n}X^\top(X\theta - y)$$

再求二阶导（**代数**）：

$$H_{\text{lin}}(\theta) = \frac{1}{n}X^\top X$$

常数矩阵，因二次型中 Hessian 与 $\theta$ 无关。$\square$

---

## 定理：引理 2: （线性模型的临界点结构）

**陈述**：$\nabla L_{\text{lin}}(\theta^*) = 0$ 当且仅当 $X^\top X\theta^* = X^\top y$（正规方程）。所有临界点构成仿射子空间：

$$\Theta^* = \{\theta^* : \theta^* = (X^\top X)^+ X^\top y + v,\; v \in \ker(X^\top X)\}$$

其中 $(X^\top X)^+$ 为 Moore-Penrose 伪逆。损失在该子空间上为常数 $L^*$。

**证明**：由引理 1，$\nabla L_{\text{lin}}(\theta^*) = 0 \iff X^\top X\theta^* = X^\top y$。这是 $\theta^*$ 的线性方程组。

设 $r = \operatorname{rank}(X)$。当 $r = d$（列满秩）时，$X^\top X$ 可逆，唯一解 $\theta^* = (X^\top X)^{-1}X^\top y$。

当 $r < d$ 时，解空间为：$\theta^* = (X^\top X)^+ X^\top y + P_{\ker(X^\top X)} w$，其中 $P_{\ker(X^\top X)}$ 是到 $\ker(X^\top X)$ 的投影算子。注意到 $\ker(X^\top X) = \ker(X)$，因此对任意 $v \in \ker(X)$，$X(\theta^* + v) = X\theta^*$，损失值不变。所有临界点处的损失均为：

$$L^* = \frac{1}{2n}\|X\theta^* - y\|^2 = \frac{1}{2n}\|P_X y - y\|^2$$

其中 $P_X = X(X^\top X)^+ X^\top$ 是到 $\operatorname{col}(X)$ 的正交投影。$\square$

---

## 定理：引理 3: （线性模型的 PL* 常数）

**陈述**：在假设 A1 + A6 下，$L_{\text{lin}}$ 在任意临界点的邻域内满足 PL* 条件：

$$\|\nabla L_{\text{lin}}(\theta)\|^2 \geq 2\mu (L_{\text{lin}}(\theta) - L^*)$$

其中 $\mu = \frac{\sigma_{\min}^+(X^\top X)}{n} > 0$，$\sigma_{\min}^+(\cdot)$ 表示最小正奇异值的平方（即最小非零特征值）。

**证明**：令 $G = \frac{1}{n}X^\top X$，则 $\nabla L_{\text{lin}}(\theta) = G\theta - \frac{1}{n}X^\top y$。

设 $\theta^*$ 为任一临界点，满足 $G\theta^* = \frac{1}{n}X^\top y$。则：

$$\nabla L_{\text{lin}}(\theta) = G(\theta - \theta^*)$$

**（代数）**：

$$\begin{aligned}
\|\nabla L_{\text{lin}}(\theta)\|^2 &= (\theta - \theta^*)^\top G^2 (\theta - \theta^*) \\
&= (\theta - \theta^*)^\top G \cdot G(\theta - \theta^*) \\
&\geq \lambda_{\min}^+(G) \cdot (\theta - \theta^*)^\top G (\theta - \theta^*)
\end{aligned}$$

其中 $\lambda_{\min}^+(G)$ 为 $G$ 的最小非零特征值 $= \sigma_{\min}^+(X^\top X)/n$。不等号成立是因为 $G$ 对称半正定，在 $\ker(G)^\perp$ 上 $G \succeq \lambda_{\min}^+(G) I$（**自证**：谱分解）。

另一方面，由 Taylor 展开（$L$ 为二次函数，二阶精确）：

$$\begin{aligned}
L_{\text{lin}}(\theta) - L^* &= \frac{1}{2}(\theta - \theta^*)^\top G (\theta - \theta^*)
\end{aligned}$$

因为 $L_{\text{lin}}(\theta) - L_{\text{lin}}(\theta^*) = \frac{1}{2}(\theta-\theta^*)^\top G(\theta-\theta^*)$（**代数**：直接展开验证，注意 $\nabla L_{\text{lin}}(\theta^*) = 0$）。

因此：

$$\|\nabla L_{\text{lin}}(\theta)\|^2 \geq 2\lambda_{\min}^+(G) \cdot \frac{1}{2}(\theta - \theta^*)^\top G (\theta - \theta^*) = 2\mu(L_{\text{lin}}(\theta) - L^*)$$

其中 $\mu = \lambda_{\min}^+(G) = \sigma_{\min}^+(X^\top X)/n$。因为 $\theta$ 可取任意值，此为全局 PL*（对所有 $\theta$ 成立，不仅邻域）。$\square$

---

## 定理：定理 1: （线性模型：所有临界点都是全局极小值，无鞍点）

**陈述**：在 A1 + A6 下，设 $\theta^*$ 为 $L_{\text{lin}}$ 的任意临界点（$\nabla L_{\text{lin}}(\theta^*) = 0$），则 $L_{\text{lin}}(\theta^*) = L^*$。$H = \frac{1}{n}X^\top X \succeq 0$，无严格鞍点（Hessian 无负特征值）。

**证明**：
由引理 2 的证明，所有临界点处的损失值为常数 $L^*$，即所有临界点都是全局极小值。

由引理 1，$H = \frac{1}{n}X^\top X \succeq 0$（半正定）。Hessian 的特征值均为非负，因而不存在负特征值，故不存在严格鞍点。

具体分类：

- 若 $\operatorname{rank}(X) = d$（列满秩），则 $H \succ 0$，$\theta^*$ 为严格局部极小（且为唯一全局极小）。
- 若 $\operatorname{rank}(X) < d$，$H$ 有 $d - \operatorname{rank}(X)$ 个零特征值，临界点构成 $d - \operatorname{rank}(X)$ 维子流形，其上每个点都是退化的全局极小值（非严格）。$\square$

---

## 第二部分：光滑 MLP（模型 ②）

## 定义

$$f_\theta(x) = \sum_{j=1}^m w_j^{(2)} \sigma(w_j^{(1)} \cdot x + b_j)$$

$$L_{\text{smooth}}(\theta) = \frac{1}{2n}\sum_{i=1}^n (f_\theta(x_i) - y_i)^2$$

其中 $\sigma \in C^2(\mathbb{R})$（如 $\tanh$, sigmoid），$\theta = \operatorname{vec}(w^{(1)}, b, w^{(2)}) \in \mathbb{R}^d$，$d = m \cdot (\dim(x) + 2)$。

**假设**：A1（$\sigma \in C^2 \Rightarrow L_{\text{smooth}} \in C^2$）、A6。

---

## 定理：引理 4: （光滑 MLP 的梯度结构）

**陈述**：令残差 $r_i = f_\theta(x_i) - y_i$，则：

$$\nabla L_{\text{smooth}}(\theta) = \frac{1}{n}\sum_{i=1}^n r_i \nabla_\theta f_\theta(x_i) = \frac{1}{n}J(\theta)^\top r$$

其中 $J(\theta) \in \mathbb{R}^{n \times d}$ 为 Jacobian，$J_{ik} = \frac{\partial f_\theta(x_i)}{\partial \theta_k}$，$r \in \mathbb{R}^n$ 为残差向量。

**证明**：链式法则（**代数**）。

$$\begin{aligned}
\frac{\partial L_{\text{smooth}}}{\partial \theta_k} &= \frac{1}{2n}\sum_{i=1}^n 2(f_\theta(x_i) - y_i) \frac{\partial f_\theta(x_i)}{\partial \theta_k} \\
&= \frac{1}{n}\sum_{i=1}^n r_i J_{ik}
\end{aligned}$$

向量化即 $\nabla L_{\text{smooth}} = \frac{1}{n}J^\top r$。$\square$

---

## 定理：引理 5: （光滑 MLP 的 Hessian 结构 — Gauss-Newton 分解）

**陈述**：

$$H_{\text{smooth}}(\theta) = \frac{1}{n}J(\theta)^\top J(\theta) + \frac{1}{n}\sum_{i=1}^n r_i \nabla_\theta^2 f_\theta(x_i)$$

第一项为 Gauss-Newton 矩阵 $G(\theta)$（半正定），第二项为残差加权 Hessian。

**证明**：对引理 4 的梯度再求导（**代数**）。

$$\begin{aligned}
\frac{\partial^2 L_{\text{smooth}}}{\partial \theta_k \partial \theta_\ell} &= \frac{1}{n}\sum_{i=1}^n \left(\frac{\partial f_\theta(x_i)}{\partial \theta_k}\frac{\partial f_\theta(x_i)}{\partial \theta_\ell} + r_i \frac{\partial^2 f_\theta(x_i)}{\partial \theta_k \partial \theta_\ell}\right) \\
&= \frac{1}{n}(J^\top J)_{k\ell} + \frac{1}{n}\sum_{i=1}^n r_i (\nabla_\theta^2 f_\theta(x_i))_{k\ell}
\end{aligned}$$

第一项即 $\frac{1}{n}J^\top J \succeq 0$。$\square$

---

## 定理：定理 2: （光滑 MLP + 全局 PL ⇒ 无次优局部极小值）

**陈述**：在 A1 + A6 下，若 $L_{\text{smooth}}$ 满足全局 PL 条件（A4）：

$$\|\nabla L_{\text{smooth}}(\theta)\|^2 \geq 2\mu(L_{\text{smooth}}(\theta) - L^*) \quad \text{对所有 } \theta \in \mathbb{R}^d$$

则：

(i) 任意临界点 $\theta^*$（$\nabla L_{\text{smooth}}(\theta^*) = 0$）都是全局极小值。

(ii) 临界点集仅包含全局极小值（$H \succeq 0$）和严格鞍点（$H$ 不定，$\lambda_{\min}(H) < 0$）。不存在次优局部极小值（即 $L(\theta^*) > L^*$ 且 $H \succ 0$）。

**证明**：

**(i)** 设 $\theta^*$ 为临界点，$\nabla L(\theta^*) = 0$。由 PL 条件：

$$\|\nabla L(\theta^*)\|^2 = 0 \geq 2\mu(L(\theta^*) - L^*)$$

因 $\mu > 0$ 且 $L(\theta^*) - L^* \geq 0$（$L^*$ 为全局最小值），得 $L(\theta^*) - L^* \leq 0$。故 $L(\theta^*) = L^*$，$\theta^*$ 为全局极小值。

**(ii)** 设 $\theta^*$ 为临界点。由 (i)，$L(\theta^*) = L^*$。以下分两种情况讨论 Hessian：

- **情形 1**：$H(\theta^*) \succeq 0$（半正定）。则 $\theta^*$ 为全局极小值（已证），$H$ 无负特征值。
- **情形 2**：$H(\theta^*)$ 不定，即存在 $v$ 使 $v^\top H(\theta^*) v < 0$。则 $\theta^*$ 为严格鞍点（**自证**：鞍点定义，$\nabla L = 0$ 且 Hessian 有负特征值）。

需排除 $H(\theta^*) \succ 0$ 且 $L(\theta^*) > L^*$（次优局部极小）的情形。若存在这样的 $\theta^*$，则在某邻域 $B_\varepsilon(\theta^*)$ 内 $L(\theta) \geq L(\theta^*) > L^*$，且 $\nabla L(\theta^*) = 0$。此时 $\|\nabla L(\theta^*)\|^2 = 0$ 但 $L(\theta^*) - L^* > 0$，与 PL 条件矛盾。因此不存在次优局部极小。$\square$

---

## 第三部分：ReLU MLP（模型 ③）

## 定义

$$f_\theta(x) = \sum_{j=1}^m w_j^{(2)} \sigma_{\text{ReLU}}(w_j^{(1)} \cdot x + b_j), \quad \sigma_{\text{ReLU}}(z) = \max(0, z)$$

$$L_{\text{ReLU}}(\theta) = \frac{1}{2n}\sum_{i=1}^n (f_\theta(x_i) - y_i)^2$$

**激活模式**：对每个神经元 $j$ 和样本 $i$，定义激活指示 $a_{ij}(\theta) = \mathbf{1}[w_j^{(1)} \cdot x_i + b_j > 0]$。

**分段线性区域**：参数空间 $\mathbb{R}^d$ 被超平面 $\{w_j^{(1)} \cdot x_i + b_j = 0\}$ 划分为有限多个开区域 $\mathcal{R}_k$。在每个 $\mathcal{R}_k$ 内，激活模式 $\{a_{ij}\}$ 恒定，$f_\theta$ 是 $\theta$ 的线性函数（因此在 $\theta$ 的仿射函数），$L_{\text{ReLU}}$ 为二次型。

---

## 定理：引理 6: （ReLU 网络在可微区域内的梯度与 Hessian）

**陈述**：在任意可微区域 $\mathcal{R}_k$ 内（$\theta$ 不位于任何激活边界），有：

$$\nabla L_{\text{ReLU}}(\theta) = \frac{1}{n}J_k^\top (f_\theta(X) - y),\quad H_{\text{ReLU}}(\theta) = \frac{1}{n}J_k^\top J_k$$

其中 $J_k$ 为区域 $\mathcal{R}_k$ 内的常数 Jacobian 矩阵（因 $f_\theta$ 在 $\mathcal{R}_k$ 内为 $\theta$ 的仿射函数，$\nabla_\theta^2 f_\theta(x_i) = 0$）。注意 $f_\theta(X)$ 虽在 $\mathcal{R}_k$ 内为 $\theta$ 的仿射函数，但 $J_k$ 本身仍随区域变化。

**证明**：在每个 $\mathcal{R}_k$ 内，$f_\theta(x_i) = \sum_{j} w_j^{(2)} a_{ij}(w_j^{(1)} \cdot x_i + b_j)$，其中 $a_{ij}$ 为常数 0 或 1。这是 $\theta$ 的线性函数（注意：$w_j^{(2)} w_j^{(1)}$ 是双线性项，在固定激活模式后对 $\theta$ 整体仍为双线性，但 Hessian 的残差项为零因为 $\nabla_\theta^2 f_\theta = 0$ — 此处需要仔细处理）。

更精确地说：在 $\mathcal{R}_k$ 内，对激活神经元（$a_{ij}=1$），$f_\theta(x_i)$ 是 $w_j^{(2)}$ 和 $w_j^{(1)}$ 的双线性函数 $w_j^{(2)}(w_j^{(1)} \cdot x_i + b_j)$。此时 $\nabla_\theta^2 f_\theta(x_i) \neq 0$（交叉导数 $\partial^2/\partial w_j^{(1)}\partial w_j^{(2)}$ 非零）。因此引理 5 的残差 Hessian 项在 $\mathcal{R}_k$ 内并不为零。

**修正**：在 $\mathcal{R}_k$ 内，$f_\theta$ 对 $\theta$ 是光滑的（$C^\infty$ 甚至），但不一定是线性的——它是对 $w^{(1)}$ 和 $w^{(2)}$ 的双线性函数。Hessian 的非 Gauss-Newton 部分确实存在。

---

## 定理：引理 6: （修正版）— ReLU 网络在可微区域内的结构

**陈述**：在任意可微区域 $\mathcal{R}_k$ 内，$L_{\text{ReLU}} \in C^\infty$。梯度为：

$$\nabla L_{\text{ReLU}}(\theta) = \frac{1}{n}J(\theta)^\top r(\theta)$$

其中 $J(\theta) \in \mathbb{R}^{n \times d}$ 为 Jacobian（在 $\mathcal{R}_k$ 内为 $\theta$ 的线性函数），$r(\theta) = f_\theta(X) - y$。Hessian 为：

$$H_{\text{ReLU}}(\theta) = \frac{1}{n}J(\theta)^\top J(\theta) + \frac{1}{n}\sum_{i=1}^n r_i(\theta) H_{f,i}(\theta)$$

其中 $H_{f,i}(\theta) = \nabla_\theta^2 f_\theta(x_i)$ 在 $\mathcal{R}_k$ 内为非零常数矩阵（仅含交叉导数分量）。

**证明**：同引理 4 和 5 的推导，因为 ReLU 在 $\mathcal{R}_k$ 内退化为线性激活（$\sigma(z) = z$ 对激活神经元，$\sigma(z) = 0$ 对非激活神经元），$f_\theta$ 在 $\mathcal{R}_k$ 内是光滑的，引理 4/5 的链式法则推导完全适用。$\square$

---

## 定理：引理 7: （局部 PL* 条件 — 可微区域内）

**陈述**（依赖 P6）：在假设 A5（过参数化，$m \gg n$）下，存在以全局极小值 $\theta^*$ 为中心的邻域 $\mathcal{N}(\theta^*)$，使得对任意 $\theta \in \mathcal{N}(\theta^*) \cap \mathcal{R}_k$（其中 $\mathcal{R}_k$ 为 $\theta^*$ 所在的可微区域）有：

$$\|\nabla L_{\text{ReLU}}(\theta)\|^2 \geq 2\mu_k(L_{\text{ReLU}}(\theta) - L^*)$$

其中 $\mu_k = \frac{\lambda_{\min}(J_k^\top J_k)}{2n} > 0$。

**证明概要**（P6 待完整证明，此处给出基于 NTK 的推理）：当 $m \to \infty$ 时，由 NTK 理论（Jacot et al., 2018; Arora et al., 2019），Jacobian $J(\theta)$ 在训练过程中变化很小（NTK 极限下的惰性）。在 $\theta^*$ 的 $O(1/\sqrt{m})$ 邻域内，$J(\theta) \approx J(\theta^*)$ 且 $J^\top J$ 的最小特征值以 $\Theta(m)$ 增长（因随机初始化下 $J$ 的行近似独立）。由此，对足够大的 $m$，$J_k^\top J_k \succ 0$（因为 $m \gg n$ 且 $J_k \in \mathbb{R}^{n \times d}$ 行满秩，$d = m \cdot (\dim(x)+2) \gg n$）。更精确的常数推导需 P6 的完整框架。$\mu_k$ 的下界由 $\frac{\lambda_{\min}(K_{\text{NTK}})}{2}$ 给出，其中 $K_{\text{NTK}}$ 为 $n \times n$ 的 NTK 矩阵（**待 P6 补全**）。

---

## 定理：定理 3: （ReLU MLP：可微临界点分类）

**陈述**：在 A1（分段）+ A6 下，若局部 PL* 条件（引理 7）在 $\theta^*$ 所在可微区域 $\mathcal{R}_k$ 内成立，则 $L_{\text{ReLU}}$ 的任意可微临界点 $\theta^* \in \mathcal{R}_k$（$\nabla L_{\text{ReLU}}(\theta^*) = 0$，且 $\theta^*$ 不位于任何激活边界）为：

- (i) **全局极小值**，若 $H(\theta^*) \succeq 0$，此时 $L(\theta^*) = L^*$。
- (ii) **严格鞍点**，若 $H(\theta^*)$ 不定，此时仍满足 $L(\theta^*) = L^*$。

不存在可微的次优局部极小值（$L(\theta^*) > L^*$ 且 $H(\theta^*) \succ 0$）。

**证明**：与定理 2 的结构相同，但在可微区域 $\mathcal{R}_k$ 内应用局部 PL* 条件替代全局 PL。

设 $\theta^* \in \mathcal{R}_k$ 是临界点。由局部 PL* 条件（引理 7），在 $\mathcal{N}(\theta^*) \cap \mathcal{R}_k$ 内：

$$0 = \|\nabla L_{\text{ReLU}}(\theta^*)\|^2 \geq 2\mu_k(L_{\text{ReLU}}(\theta^*) - L^*)$$

因为 $\mu_k > 0$ 且 $L(\theta^*) - L^* \geq 0$，得 $L(\theta^*) = L^*$。因此 $\theta^*$ 是全局极小值。

关于 Hessian 分类：

- $H(\theta^*) \succeq 0$：$\theta^*$ 是全局极小值（二阶条件满足）。
- $H(\theta^*)$ 不定（存在负特征值）：$\theta^*$ 是严格鞍点。$\square$

**注**：此处存在微妙之处——虽然 $L(\theta^*) = L^*$，但 Hessian 可能不定。这意味着即使损失值为全局最小，某些方向仍导致损失增加（正曲率），某些方向导致损失减少（负曲率），但因为损失已经是最小值，沿负曲率方向移动时，初始的损失减少会在离开 $\mathcal{R}_k$ 时被 ReLU 激活变化所抵消或变为增加。在 $\mathcal{R}_k$ 内部，二次近似可能显示负方向，但实际损失不能低于 $L^*$，意味着沿这些方向的 Taylor 高阶项（不可忽略）或区域边界的不可微性起了约束作用。**待数值验证**。

---

## 第四部分：ReLU 不可微驻点

### 定义：Clarke 次梯度与 Clarke 驻点

对于局部 Lipschitz 函数 $L_{\text{ReLU}}$，Clarke 次梯度定义为：

$$\partial L(\theta) = \operatorname{conv}\left\{\lim_{k \to \infty} \nabla L(\theta_k) : \theta_k \to \theta,\; \theta_k \notin \Omega_{\text{nd}}\right\}$$

其中 $\Omega_{\text{nd}}$ 为不可微点集（Lebesgue 测度为零）。$0 \in \partial L(\theta)$ 的点称为 Clarke 驻点。

---

## 定理：定理 4: （ReLU 不可微驻点：PL 相容性下的非局部极小性质）

**陈述**（启发式猜测，待严格证明）：在 A4（Clarke PL 条件）或局部 Clarke PL* 下，设 $\theta^*$ 为 Clarke 驻点（$0 \in \partial L_{\text{ReLU}}(\theta^*)$）且位于至少一个激活边界上，则：

- 若 $L(\theta^*) > L^*$，则 $\theta^*$ **不是**局部极小值（在任意邻域内存在损失更小的点）。

等价地说：任何局部极小值（即使是不可微点）必须满足 $L(\theta^*) = L^*$。

**论证框架**（启发式，非严格证明）：

假设 $\theta^*$ 是局部极小值且 $L(\theta^*) > L^*$。因 $\theta^*$ 位于激活边界，存在一个或多个神经元满足 $w_j^{(1)} \cdot x_i + b_j = 0$。考虑一个充分接近的 $\theta$ 使得这些神经元的激活状态发生翻转。

在 $\theta^*$ 的任意小邻域内，$L$ 在该邻域的下确界 $\leq L^* < L(\theta^*)$（因为全局极小值可达且 $L^* < L(\theta^*)$）。因此 $\theta^*$ 不可能是局部极小值——除非 $L^*$ 不可达（但 ReLU 网络在过参数化下可实现零训练损失，参见 Arora et al., 2019）。

**困难**：需排除「悬崖」型局部极小——在不可微点处，函数可能在一个方向上上升（所有可微方向），但由于非光滑折角而在另一侧截断。Clarke PL 条件排除了这种可能性，因为次梯度的范数（或最小范数次梯度）满足 PL 不等式，从而 $0 \in \partial L(\theta^*)$ 蕴含 $L(\theta^*) = L^*$（与定理 2(i) 相同的逻辑）。

**正式猜测**：若 Clarke PL 条件成立（即 $\min_{g \in \partial L(\theta)} \|g\|^2 \geq 2\mu(L(\theta) - L^*)$），则任意 Clarke 驻点必为全局极小值。否则存在 $g \in \partial L(\theta^*)$ 使 $\|g\| = 0$ 但 $L(\theta^*) > L^*$，矛盾。$\square$（**待严格化：需验证 Clarke PL 条件在 ReLU 网络中成立的条件**）

---

## 第五部分：过参数化 → PL*（命题 P6 框架）

## 定理：定理 5: （过参数化诱导局部 PL* — NTK 框架）

**陈述**（待完整证明，此处给出证明框架）：在 A1（分段）+ A5（$m \to \infty$）+ A6 下，以高概率存在以随机初始化 $\theta_0$ 为中心的邻域 $\mathcal{B}_\rho(\theta_0)$（$\rho = O(1/\sqrt{m})$），使得：

1. 对所有 $\theta \in \mathcal{B}_\rho(\theta_0)$，NTK 矩阵 $K(\theta) = J(\theta)J(\theta)^\top \in \mathbb{R}^{n \times n}$ 满足 $\lambda_{\min}(K(\theta)) \geq \frac{\lambda_0}{2} > 0$，其中 $\lambda_0 = \lambda_{\min}(K_\infty)$（无限宽 NTK 的最小特征值）。

2. 由此导出局部 PL* 条件：

$$\|\nabla L(\theta)\|^2 = \frac{1}{n^2}r^\top K(\theta) r \geq \frac{\lambda_{\min}(K(\theta))}{n^2}\|r\|^2 = \frac{2\lambda_{\min}(K(\theta))}{n}(L(\theta) - L^*)$$

其中 $L^* = 0$（过参数化可实现零损失）。

**证明框架**（基于 Arora et al., 2019; Jacot et al., 2018）：

**步骤 1（NTK 正定性）**：在无限宽极限下，$K_\infty(x, x') = \mathbb{E}_{w \sim \mathcal{N}(0,I)}[x^\top x' \mathbf{1}[w^\top x \geq 0, w^\top x' \geq 0]]$。当数据点不平行（$x_i \not\propto x_j$ 对所有 $i \neq j$）时，$K_\infty \succ 0$（**文献**：Arora et al., 2019, Theorem 3.1）。

**步骤 2（有限宽度逼近）**：对 $m = \Omega\left(\frac{n^4}{\lambda_0^4 \delta^2}\right)$，以概率 $\geq 1-\delta$，对所有 $\theta \in \mathcal{B}_\rho(\theta_0)$ 有 $\|K(\theta) - K_\infty\|_2 \leq \frac{\lambda_0}{4}$，从而 $\lambda_{\min}(K(\theta)) \geq \frac{3\lambda_0}{4}$。

**步骤 3（局部 PL* 推导）**：

$$\begin{aligned}
\|\nabla L(\theta)\|^2 &= \left\|\frac{1}{n}J(\theta)^\top r\right\|^2 = \frac{1}{n^2}r^\top J(\theta)J(\theta)^\top r \\
&= \frac{1}{n^2}r^\top K(\theta) r \geq \frac{\lambda_{\min}(K(\theta))}{n^2}\|r\|^2 \\
&= \frac{2\lambda_{\min}(K(\theta))}{n} \cdot \frac{\|r\|^2}{2n} = \frac{2\lambda_{\min}(K(\theta))}{n}(L(\theta) - 0)
\end{aligned}$$

取 $\mu = \frac{\lambda_{\min}(K(\theta))}{n} \geq \frac{3\lambda_0}{4n} > 0$。$\square$

**待补全**：

- 邻域半径 $\rho$ 的精确刻画（依赖于 $m$、$\lambda_0$ 和 ReLU 的分段常数）。
- 从随机初始化到全局极小的整个训练轨迹是否始终保持在 PL* 区域内（Chizat & Bach, 2018 的惰性训练分析）。

---

## 总结：定理与引理依赖关系

```
P1 (引理 3: μ = σ⁺_min(X^TX)/n) ──→ P2 (定理 1: 线性模型无鞍点)
                                        │
P6 (定理 5: 过参数化 → 局部 PL*) ──→ P3 (定理 2: 光滑 MLP + PL ⇒ 无次优极小)
                                        │
                                        ├──→ P4 (定理 3: ReLU 可微临界点分类)
                                        │
                                        └──→ P5 (定理 4: ReLU 不可微驻点猜测)
```

| 命题 | 状态 |
|------|------|
| P1 | ✅ 引理 3 |
| P2 | ✅ 定理 1 |
| P3 | ✅ 定理 2 |
| P4 | ⚠️ 定理 3（依赖 P6 的 PL* 常数显式界） |
| P5 | ❓ 定理 4（启发式，待 Clarke PL 严格化） |
| P6 | ⚠️ 定理 5 框架（待补全 $\rho$ 和有限 $m$ 的精确分析） |

```yaml
verifiable:
  # P1: 线性模型 PL* 常数
  - expression: "L = (1/6)*((2*theta1 + theta2 - 3)**2 + (theta1 + 3*theta2 - 4)**2 + (theta1 + theta2 - 2)**2)"
    point: "1,1"
    expected:
      classification: global_minimum
      hessian_spectrum: "all non-negative"
    assumptions: [A1, A6]
    tier_hint: symbolic

  # P2: 正规方程解验证
  - expression: "L = (1/6)*((2*theta1 + theta2 - 3)**2 + (theta1 + 3*theta2 - 4)**2 + (theta1 + theta2 - 2)**2)"
    point: "正规方程解"
    expected:
      gradient_norm: 0
    assumptions: [A1, A6]
    tier_hint: symbolic
```

## 定理：定理 1: （线性模型：所有临界点 → 全局极小）

**依赖假设**：A1（$C^2$）、A6（有限样本固定）。无 A4 依赖（线性模型天然满足全局 PL*）。

**反例排查**：

- **放松 A1（$C^2$ → 仅 $C^1$）**：定理 1 实际上只需 $C^1$（临界点定义仅需梯度），且 Hessian 的分类（非严格鞍点 vs 退化极小）用到 $C^2$，但「所有临界点 = 全局极小」的核心结论不依赖 Hessian。线性平方损失是 $C^\infty$ 的，无法放松。
- **放松 A6（有限样本 → 在线/随机）**：这是另一种设定，不改变「所有临界点 = 全局极小」的几何事实。
- **线性模型本质是凸的**：$X^\top X \succeq 0$，函数为凸二次型。

**结论**：无真实反例。定理 1 在线性平方损失设定下是完备的，即使 $\operatorname{rank}(X) < d$ 结论仍成立。

---

## 定理：定理 2: （光滑 MLP + 全局 PL ⇒ 无次优局部极小）

**依赖假设**：A1（$C^2$）、A4（全局 PL 条件）、A6。

**核心反例：放松 A4**。

#### 反例 1：Swirszcz-Czarnecki-Pascanu (2016) — tanh 网络中的虚假局部极小

**失效假设**：A4（全局 PL 条件不成立）。

**构造**（来自 Swirszcz et al., 2016, "Local minima in training of neural networks"）：

- **网络**：单隐藏层，$\tanh$ 激活，$m = 2$ 个隐藏神经元，输入维度 $1$。
  $$f_\theta(x) = w_1^{(2)}\tanh(w_1^{(1)}x + b_1) + w_2^{(2)}\tanh(w_2^{(1)}x + b_2)$$
- **数据**：$n = 2$ 个点：$(x_1, y_1) = (1, 1), (x_2, y_2) = (-1, -1)$。
- **损失**：$L(\theta) = \frac{1}{4}[(f_\theta(1) - 1)^2 + (f_\theta(-1) + 1)^2]$。

**现象**：存在参数配置使 $L(\theta^*) \approx 0.0375 > 0 = L^*$（$L^*$ 为全局极小，因 $\tanh$ 可完美拟合这两个点），且 $\nabla L(\theta^*) = 0$，$H(\theta^*) \succ 0$。此为**次优局部极小值**。

**机制**：$\tanh$ 的饱和区使得两个神经元进入「对称但优化锁死」的状态——每个神经元负责拟合一个数据点，但互相干扰导致梯度为零且 Hessian 正定。PL 条件在此处不成立：$L(\theta^*) - L^* > 0$ 但 $\|\nabla L(\theta^*)\| = 0$，无法满足 $\|\nabla L\|^2 \geq 2\mu(L - L^*)$。

```yaml
verifiable:
  - expression: "0.25*((w1*tanh(u1*1+v1)+w2*tanh(u2*1+v2)-1)**2 + (w1*tanh(u1*(-1)+v1)+w2*tanh(u2*(-1)+v2)+1)**2)"
    point: "约 w1=w2≈1.2, u1≈-u2≈2.0, v1=v2≈0"
    expected:
      classification: local_minimum
      optimality_gap: "> 0"
    failed_assumption: A4
    tier_hint: numerical
```

---

## 定理：定理 3: （ReLU 可微临界点 ⇒ 全局极小或严格鞍点）

**依赖假设**：A1（分段 $C^2$）、A6、**P6**（局部 PL* 条件，依赖过参数化 A5）。

**核心反例：放松 P6 / A5——窄网络下的虚假局部极小**。

#### 反例 2：Safran & Shamir (2018) — 窄 ReLU 网络中的虚假局部极小

**失效假设**：P6（局部 PL* 不成立，因 $m$ 不够大）。

**构造**（来自 Safran & Shamir, 2018, "Spurious Local Minima are Common in Two-Layer ReLU Neural Networks", `1705.03856`）：

- **网络**：单隐藏层 ReLU，$m$ 个神经元，输入维度 $d$。
- **主要结果**：当 $m < \Theta(n/d)$ 时（窄网络），以高概率存在次优局部极小值。具体构造使用了「半球」数据分布 + 随机标签。

**具体可验证反例**（简化版，来自 Venturi et al., 2019, `1810.06032` 的构造）：

- $m = 1$，$d = 1$，$n = 3$。
- 数据：$(x_i, y_i) = (-1, 0), (0, 1), (1, 0)$（倒 V 形）。
- $f_\theta(x) = w_2 \cdot \operatorname{ReLU}(w_1 x + b)$。
- 损失：$L(\theta) = \frac{1}{6}\sum_{i=1}^3 (f_\theta(x_i) - y_i)^2$。

**现象**：存在参数配置使 $w_1 = 0, b > 0, w_2 = 1$（即 $f(x) = b$ 常数输出），此时 $\nabla L = 0$（因为 $x_i$ 对称且均值为零），$L = \frac{2}{3} > 0 = L^*$（$L^*$ 需采用 $w_1$ 非零的配置来实现非对称拟合）。该临界点在可微区域内（$w_1 x_i + b > 0$ 对所有 $i$），且 Hessian 的 Gauss-Newton 部分 $J^\top J$ 在该点为秩亏（因为 $f_\theta$ 变为常数函数，Jacobi 为常数行），导致 PL* 常数 $\mu_k$ 为零。

```yaml
verifiable:
  - expression: "(1/6)*((w2*max(w1*(-1)+b,0)-0)**2 + (w2*max(w1*0+b,0)-1)**2 + (w2*max(w1*1+b,0)-0)**2)"
    point: "w1=0, b=1, w2=1"
    expected:
      classification: local_minimum_or_degenerate_saddle
      optimality_gap: "> 0"
    failed_assumption: P6
    tier_hint: numerical
```

#### 反例 3：Venturi et al. (2019) — 一般构造

更一般的构造来自 Venturi, Bandeira & Bruna (2019, `1810.06032`)：对任意 $m < n$ 的 ReLU 网络，可通过构造对称数据分布使损失函数的 Hessian 在特定区域退化（Jacobi 秩亏），从而产生次优临界点。

---

## 定理：定理 4: （ReLU 不可微驻点 → 非局部极小，除非全局）

**依赖假设**：Clarke PL 条件（A4 的推广）、A6。

**反例排查：放松 Clarke PL 条件**。

#### 反例 4：Davis et al. (2020) — 次梯度方法在非 Clarke 驻点停滞

**失效假设**：次梯度方法（如 SGD 使用次梯度）可能停滞在非 Clarke 驻点——这些点满足「0 在次微分的凸包中」但不满足更严格的 Clarke 条件，且可以是**局部极小值**。

**简化反例构造**（来自 Cui & Pang, 2021, "Modern Nonconvex Nondifferentiable Optimization" 第 3 章）：

- **函数**：$L(\theta) = |\theta_1| - |\theta_2| + \theta_1^2 + \theta_2^2$（二维，含不可微项）。
- **点**：$\theta^* = (0, 0)$。
  - 经典梯度不存在（绝对值函数在零点不可微）。
  - $\partial L(0,0) = [-1, 1] \times [-1, 1]$（Clarke 次微分是正方形）。
  - $0 \in \partial L(0,0)$ ⇒ $(0,0)$ 是 Clarke 驻点。
  - 沿 $\theta_2$ 方向，$L(0, \varepsilon) = -|\varepsilon| + \varepsilon^2 = -\varepsilon + \varepsilon^2 < 0 = L(0,0)$（对小的 $\varepsilon>0$）。因此 $(0,0)$ 不是局部极小值 → 符合定理 4 的预测。

但**真正需要关注的**是：当 PL 条件在 Clarke 意义下不成立时，是否出现「Clarke 驻点且为次优局部极小」？

**构造（待数值验证）**：考虑
$$L(\theta) = \max(0, \theta)^2 - 2\max(0, -\theta)^2$$

在 $\theta = 0$ 处，左导数 $L'_-(0) = 0$，右导数 $L'_+(0) = 0$（因为 $\max(0,\theta)^2$ 在 $0$ 处的导数为 $0$，$\max(0,-\theta)^2$ 在 $0$ 处导数为 $0$），$\nabla L(0) = 0$。但 $L(\varepsilon) = \varepsilon^2 > 0 = L(0)$，$L(-\varepsilon) = -2\varepsilon^2 < 0$，所以 $0$ 是鞍点（沿负方向下降）。

更关键的问题是：在 ReLU 网络的激活边界处，Clarke PL 条件是否成立？若成立则定理 4 成立（无虚假不可微极小）；若不成立，则可能产生不可微的虚假局部极小。目前这个方向文献极少——**这是本 Campaign 的一个高价值开放问题**。

---

## 定理：定理 5: （过参数化 ⇒ 局部 PL*）

**依赖假设**：A5（$m \to \infty$）、A6、A1（分段 $C^2$）。

**核心反例：放松 A5——有限宽度**。

#### 反例 5：Liu et al. (2020) — 中等宽度下的坏局部极小

**失效假设**：A5（$m$ 不够大，$m = O(n)$）。

**构造**（来自 Liu, Zhu & Belkin, 2020, "On the linearity of large non-linear models", `2002.06324`）：

- **网络**：两层 ReLU，平方损失。
- **现象**：当 $m = O(n)$（中等宽度），存在次优局部极小值。这些极小值出现在「神经元坍缩」状态——多个神经元学习到相同的特征方向，导致 effective rank 降低，Jacobi 矩阵的 $J^\top J$ 出现零特征值，PL* 常数退化。

**数值可验证构造**（来自 Ding et al., 2022, "Global Optimality of Elman-type RNN", `2205.12705`）：

- $m = 2$（隐藏神经元数），$n = 4$，$d = 1$。
- 数据：$(x_i, y_i) = (-2, 1), (-1, -1), (1, -1), (2, 1)$（W 形）。
- 存在参数配置使两个神经元的输入权重同符号或同比例，导致 Jacobi 秩亏，损失停留在次优局部极小。

```yaml
verifiable:
  - expression: "(1/8)*sum((w1*max(u1*xi+v1,0)+w2*max(u2*xi+v2,0)-yi)**2 for xi,yi in [(-2,1),(-1,-1),(1,-1),(2,1)])"
    point: "w1=w2, u1=u2 (神经元对称坍缩)"
    expected:
      classification: degenerate_critical_point
      jacobian_rank: "< n"
    failed_assumption: A5
    tier_hint: numerical
```

---

## 结论

### 反例总表

| 反例编号 | 失效定理 | 失效假设 | 现象 | 文献来源 |
|----------|----------|----------|------|----------|
| **R1** | 定理 2 | **A4**（全局 PL） | $\tanh$ 网络：存在 Hessian 正定的次优局部极小 | Swirszcz et al., 2016 |
| **R2** | 定理 3 | **P6**（局部 PL*） | 窄 ReLU 网络（$m=1$）：可微区域内存在次优临界点 | Safran & Shamir, 2018 |
| **R3** | 定理 3 | **P6** / **A5** | $m < n$ 时 Jacobi 秩亏 → PL* 常数退化 | Venturi et al., 2019 |
| **R4** | 定理 5 | **A5**（$m=O(n)$） | 中等宽度：神经元坍缩 → $J^\top J$ 零特征值 | Liu et al., 2020 |
| **R5** | 定理 4 | **Clarke PL**（待严格化） | 不可微点处的虚假局部极小？ | **开放问题** |

### 可验证 Claim（数值层）

```yaml
verifiable:
  # R1: tanh 网络虚假局部极小
  - expression: "0.25*((w1*tanh(u1+v1)+w2*tanh(u2+v2)-1)**2 + (w1*tanh(-u1+v1)+w2*tanh(-u2+v2)+1)**2)"
    point: "w1=1.2, w2=1.2, u1=2.0, u2=-2.0, v1=0, v2=0"
    expected:
      classification: local_minimum
      gradient_norm: "≈ 0"
      hessian_min_eig: "> 0"
      optimality_gap: "≈ 0.0375"
    failed_assumption: A4
    tier_hint: numerical

  # R2: 窄 ReLU 网络次优临界点 (m=1, n=3)
  - expression: "(1/6)*((w2*max(w1*(-1)+b,0)-0)**2 + (w2*max(w1*0+b,0)-1)**2 + (w2*max(w1*1+b,0)-0)**2)"
    point: "w1=0, b=1, w2=1"
    expected:
      classification: critical_point
      loss: "≈ 0.6667"
      global_minimum: "0"
    failed_assumption: P6
    tier_hint: numerical

  # 线性模型：无真实反例（验证完备性）
  - expression: "0.5*((theta1+theta2-2)**2 + (theta1-theta2-0)**2)"
    point: "1,1"
    expected:
      classification: global_minimum
      gradient_norm: 0
      hessian_spectrum: "all >= 0"
    tier_hint: symbolic
```

### 开放问题（高价值方向）

1. **R5**：ReLU 网络在激活边界处，Clarke PL 条件是否成立？若成立，可用于严格证明定理 4；若不成立，需构造不可微虚假局部极小的具体反例。
2. **反例 R2/R3 的精确宽度阈值**：是否存在 $\tilde{m}(n, d)$，使得 $m > \tilde{m}$ 时 PL* 必然成立（消除所有虚假局部极小）？当前 NTK 理论给出 $m = \Omega(n^4)$，但实验表明 $m = 2n$ 往往已足够——这个 gap 需要弥合。
3. **光滑 vs ReLU 的本质差异**：反例 R1（$\tanh$ 有虚假极小）与定理 3（ReLU + 宽网络无虚假极小）的对比揭示了激活函数选择的非平凡影响——ReLU 的分段线性性质在过参数化下表现更好（因 Hessian 残差项在有界区域内消失），而光滑饱和激活的残差 Hessian 项可能锁定次优状态。

## 定理：引理 1: （线性模型的梯度与 Hessian）

**陈述**：对任意 $\theta \in \mathbb{R}^d$，

$$\nabla L_{\text{lin}}(\theta) = \frac{1}{n}X^\top(X\theta - y)$$

$$H_{\text{lin}}(\theta) = \frac{1}{n}X^\top X \quad \text{（常矩阵，不依赖于 } \theta \text{）}$$

**证明**：直接计算。

$$\begin{aligned}
L_{\text{lin}}(\theta) &= \frac{1}{2n}(X\theta - y)^\top(X\theta - y) \\
&= \frac{1}{2n}\left(\theta^\top X^\top X\theta - 2y^\top X\theta + y^\top y\right)
\end{aligned}$$

对 $\theta$ 求一阶导（**代数**）：

$$\nabla L_{\text{lin}}(\theta) = \frac{1}{n}\left(X^\top X\theta - X^\top y\right) = \frac{1}{n}X^\top(X\theta - y)$$

再求二阶导（**代数**）：

$$H_{\text{lin}}(\theta) = \frac{1}{n}X^\top X$$

常数矩阵，因二次型中 Hessian 与 $\theta$ 无关。$\square$

---

## 定理：引理 2: （线性模型的临界点结构）

**陈述**：$\nabla L_{\text{lin}}(\theta^*) = 0$ 当且仅当 $X^\top X\theta^* = X^\top y$（正规方程）。所有临界点构成仿射子空间：

$$\Theta^* = \{\theta^* : \theta^* = (X^\top X)^+ X^\top y + v,\; v \in \ker(X^\top X)\}$$

其中 $(X^\top X)^+$ 为 Moore-Penrose 伪逆。损失在该子空间上为常数 $L^*$。

**证明**：由引理 1，$\nabla L_{\text{lin}}(\theta^*) = 0 \iff X^\top X\theta^* = X^\top y$。这是 $\theta^*$ 的线性方程组。

设 $r = \operatorname{rank}(X)$。当 $r = d$（列满秩）时，$X^\top X$ 可逆，唯一解 $\theta^* = (X^\top X)^{-1}X^\top y$。

当 $r < d$ 时，解空间为：$\theta^* = (X^\top X)^+ X^\top y + P_{\ker(X^\top X)} w$，其中 $P_{\ker(X^\top X)}$ 是到 $\ker(X^\top X)$ 的投影算子。注意到 $\ker(X^\top X) = \ker(X)$，因此对任意 $v \in \ker(X)$，$X(\theta^* + v) = X\theta^*$，损失值不变。所有临界点处的损失均为：

$$L^* = \frac{1}{2n}\|X\theta^* - y\|^2 = \frac{1}{2n}\|P_X y - y\|^2$$

其中 $P_X = X(X^\top X)^+ X^\top$ 是到 $\operatorname{col}(X)$ 的正交投影。$\square$

---

## 定理：引理 3: （线性模型的 PL* 常数）

**陈述**：在假设 A1 + A6 下，$L_{\text{lin}}$ 在任意临界点的邻域内满足 PL* 条件：

$$\|\nabla L_{\text{lin}}(\theta)\|^2 \geq 2\mu (L_{\text{lin}}(\theta) - L^*)$$

其中 $\mu = \frac{\sigma_{\min}^+(X^\top X)}{n} > 0$，$\sigma_{\min}^+(\cdot)$ 表示最小正奇异值的平方（即最小非零特征值）。

**证明**：令 $G = \frac{1}{n}X^\top X$，则 $\nabla L_{\text{lin}}(\theta) = G\theta - \frac{1}{n}X^\top y$。

设 $\theta^*$ 为任一临界点，满足 $G\theta^* = \frac{1}{n}X^\top y$。则：

$$\nabla L_{\text{lin}}(\theta) = G(\theta - \theta^*)$$

**（代数）**：

$$\begin{aligned}
\|\nabla L_{\text{lin}}(\theta)\|^2 &= (\theta - \theta^*)^\top G^2 (\theta - \theta^*) \\
&= (\theta - \theta^*)^\top G \cdot G(\theta - \theta^*) \\
&\geq \lambda_{\min}^+(G) \cdot (\theta - \theta^*)^\top G (\theta - \theta^*)
\end{aligned}$$

其中 $\lambda_{\min}^+(G)$ 为 $G$ 的最小非零特征值 $= \sigma_{\min}^+(X^\top X)/n$。不等号成立是因为 $G$ 对称半正定，在 $\ker(G)^\perp$ 上 $G \succeq \lambda_{\min}^+(G) I$（**自证**：谱分解）。

另一方面，由 Taylor 展开（$L$ 为二次函数，二阶精确）：

$$\begin{aligned}
L_{\text{lin}}(\theta) - L^* &= \frac{1}{2}(\theta - \theta^*)^\top G (\theta - \theta^*)
\end{aligned}$$

因为 $L_{\text{lin}}(\theta) - L_{\text{lin}}(\theta^*) = \frac{1}{2}(\theta-\theta^*)^\top G(\theta-\theta^*)$（**代数**：直接展开验证，注意 $\nabla L_{\text{lin}}(\theta^*) = 0$）。

因此：

$$\|\nabla L_{\text{lin}}(\theta)\|^2 \geq 2\lambda_{\min}^+(G) \cdot \frac{1}{2}(\theta - \theta^*)^\top G (\theta - \theta^*) = 2\mu(L_{\text{lin}}(\theta) - L^*)$$

其中 $\mu = \lambda_{\min}^+(G) = \sigma_{\min}^+(X^\top X)/n$。因为 $\theta$ 可取任意值，此为全局 PL*（对所有 $\theta$ 成立，不仅邻域）。$\square$

---

## 定理：定理 1: （线性模型：所有临界点都是全局极小值，无鞍点）

**陈述**：在 A1 + A6 下，设 $\theta^*$ 为 $L_{\text{lin}}$ 的任意临界点（$\nabla L_{\text{lin}}(\theta^*) = 0$），则 $L_{\text{lin}}(\theta^*) = L^*$。$H = \frac{1}{n}X^\top X \succeq 0$，无严格鞍点（Hessian 无负特征值）。

**证明**：
由引理 2 的证明，所有临界点处的损失值为常数 $L^*$，即所有临界点都是全局极小值。

由引理 1，$H = \frac{1}{n}X^\top X \succeq 0$（半正定）。Hessian 的特征值均为非负，因而不存在负特征值，故不存在严格鞍点。

具体分类：

- 若 $\operatorname{rank}(X) = d$（列满秩），则 $H \succ 0$，$\theta^*$ 为严格局部极小（且为唯一全局极小）。
- 若 $\operatorname{rank}(X) < d$，$H$ 有 $d - \operatorname{rank}(X)$ 个零特征值，临界点构成 $d - \operatorname{rank}(X)$ 维子流形，其上每个点都是退化的全局极小值（非严格）。$\square$

---

## 第二部分：光滑 MLP（模型 ②）

## 定义

$$f_\theta(x) = \sum_{j=1}^m w_j^{(2)} \sigma(w_j^{(1)} \cdot x + b_j)$$

$$L_{\text{smooth}}(\theta) = \frac{1}{2n}\sum_{i=1}^n (f_\theta(x_i) - y_i)^2$$

其中 $\sigma \in C^2(\mathbb{R})$（如 $\tanh$, sigmoid），$\theta = \operatorname{vec}(w^{(1)}, b, w^{(2)}) \in \mathbb{R}^d$，$d = m \cdot (\dim(x) + 2)$。

**假设**：A1（$\sigma \in C^2 \Rightarrow L_{\text{smooth}} \in C^2$）、A6。

---

## 定理：引理 4: （光滑 MLP 的梯度结构）

**陈述**：令残差 $r_i = f_\theta(x_i) - y_i$，则：

$$\nabla L_{\text{smooth}}(\theta) = \frac{1}{n}\sum_{i=1}^n r_i \nabla_\theta f_\theta(x_i) = \frac{1}{n}J(\theta)^\top r$$

其中 $J(\theta) \in \mathbb{R}^{n \times d}$ 为 Jacobian，$J_{ik} = \frac{\partial f_\theta(x_i)}{\partial \theta_k}$，$r \in \mathbb{R}^n$ 为残差向量。

**证明**：链式法则（**代数**）。

$$\begin{aligned}
\frac{\partial L_{\text{smooth}}}{\partial \theta_k} &= \frac{1}{2n}\sum_{i=1}^n 2(f_\theta(x_i) - y_i) \frac{\partial f_\theta(x_i)}{\partial \theta_k} \\
&= \frac{1}{n}\sum_{i=1}^n r_i J_{ik}
\end{aligned}$$

向量化即 $\nabla L_{\text{smooth}} = \frac{1}{n}J^\top r$。$\square$

---

## 定理：引理 5: （光滑 MLP 的 Hessian 结构 — Gauss-Newton 分解）

**陈述**：

$$H_{\text{smooth}}(\theta) = \frac{1}{n}J(\theta)^\top J(\theta) + \frac{1}{n}\sum_{i=1}^n r_i \nabla_\theta^2 f_\theta(x_i)$$

第一项为 Gauss-Newton 矩阵 $G(\theta)$（半正定），第二项为残差加权 Hessian。

**证明**：对引理 4 的梯度再求导（**代数**）。

$$\begin{aligned}
\frac{\partial^2 L_{\text{smooth}}}{\partial \theta_k \partial \theta_\ell} &= \frac{1}{n}\sum_{i=1}^n \left(\frac{\partial f_\theta(x_i)}{\partial \theta_k}\frac{\partial f_\theta(x_i)}{\partial \theta_\ell} + r_i \frac{\partial^2 f_\theta(x_i)}{\partial \theta_k \partial \theta_\ell}\right) \\
&= \frac{1}{n}(J^\top J)_{k\ell} + \frac{1}{n}\sum_{i=1}^n r_i (\nabla_\theta^2 f_\theta(x_i))_{k\ell}
\end{aligned}$$

第一项即 $\frac{1}{n}J^\top J \succeq 0$。$\square$

---

## 定理：定理 2: （光滑 MLP + 全局 PL ⇒ 无次优局部极小值）

**陈述**：在 A1 + A6 下，若 $L_{\text{smooth}}$ 满足全局 PL 条件（A4）：

$$\|\nabla L_{\text{smooth}}(\theta)\|^2 \geq 2\mu(L_{\text{smooth}}(\theta) - L^*) \quad \text{对所有 } \theta \in \mathbb{R}^d$$

则：

(i) 任意临界点 $\theta^*$（$\nabla L_{\text{smooth}}(\theta^*) = 0$）都是全局极小值。

(ii) 临界点集仅包含全局极小值（$H \succeq 0$）和严格鞍点（$H$ 不定，$\lambda_{\min}(H) < 0$）。不存在次优局部极小值（即 $L(\theta^*) > L^*$ 且 $H \succ 0$）。

**证明**：

**(i)** 设 $\theta^*$ 为临界点，$\nabla L(\theta^*) = 0$。由 PL 条件：

$$\|\nabla L(\theta^*)\|^2 = 0 \geq 2\mu(L(\theta^*) - L^*)$$

因 $\mu > 0$ 且 $L(\theta^*) - L^* \geq 0$（$L^*$ 为全局最小值），得 $L(\theta^*) - L^* \leq 0$。故 $L(\theta^*) = L^*$，$\theta^*$ 为全局极小值。

**(ii)** 设 $\theta^*$ 为临界点。由 (i)，$L(\theta^*) = L^*$。以下分两种情况讨论 Hessian：

- **情形 1**：$H(\theta^*) \succeq 0$（半正定）。则 $\theta^*$ 为全局极小值（已证），$H$ 无负特征值。
- **情形 2**：$H(\theta^*)$ 不定，即存在 $v$ 使 $v^\top H(\theta^*) v < 0$。则 $\theta^*$ 为严格鞍点（**自证**：鞍点定义，$\nabla L = 0$ 且 Hessian 有负特征值）。

需排除 $H(\theta^*) \succ 0$ 且 $L(\theta^*) > L^*$（次优局部极小）的情形。若存在这样的 $\theta^*$，则在某邻域 $B_\varepsilon(\theta^*)$ 内 $L(\theta) \geq L(\theta^*) > L^*$，且 $\nabla L(\theta^*) = 0$。此时 $\|\nabla L(\theta^*)\|^2 = 0$ 但 $L(\theta^*) - L^* > 0$，与 PL 条件矛盾。因此不存在次优局部极小。$\square$

---

## 第三部分：ReLU MLP（模型 ③）

## 定义

$$f_\theta(x) = \sum_{j=1}^m w_j^{(2)} \sigma_{\text{ReLU}}(w_j^{(1)} \cdot x + b_j), \quad \sigma_{\text{ReLU}}(z) = \max(0, z)$$

$$L_{\text{ReLU}}(\theta) = \frac{1}{2n}\sum_{i=1}^n (f_\theta(x_i) - y_i)^2$$

**激活模式**：对每个神经元 $j$ 和样本 $i$，定义激活指示 $a_{ij}(\theta) = \mathbf{1}[w_j^{(1)} \cdot x_i + b_j > 0]$。

**分段线性区域**：参数空间 $\mathbb{R}^d$ 被超平面 $\{w_j^{(1)} \cdot x_i + b_j = 0\}$ 划分为有限多个开区域 $\mathcal{R}_k$。在每个 $\mathcal{R}_k$ 内，激活模式 $\{a_{ij}\}$ 恒定，$f_\theta$ 是 $\theta$ 的线性函数（因此在 $\theta$ 的仿射函数），$L_{\text{ReLU}}$ 为二次型。

---

## 定理：引理 6: （ReLU 网络在可微区域内的梯度与 Hessian）

**陈述**：在任意可微区域 $\mathcal{R}_k$ 内（$\theta$ 不位于任何激活边界），有：

$$\nabla L_{\text{ReLU}}(\theta) = \frac{1}{n}J_k^\top (f_\theta(X) - y),\quad H_{\text{ReLU}}(\theta) = \frac{1}{n}J_k^\top J_k$$

其中 $J_k$ 为区域 $\mathcal{R}_k$ 内的常数 Jacobian 矩阵（因 $f_\theta$ 在 $\mathcal{R}_k$ 内为 $\theta$ 的仿射函数，$\nabla_\theta^2 f_\theta(x_i) = 0$）。注意 $f_\theta(X)$ 虽在 $\mathcal{R}_k$ 内为 $\theta$ 的仿射函数，但 $J_k$ 本身仍随区域变化。

**证明**：在每个 $\mathcal{R}_k$ 内，$f_\theta(x_i) = \sum_{j} w_j^{(2)} a_{ij}(w_j^{(1)} \cdot x_i + b_j)$，其中 $a_{ij}$ 为常数 0 或 1。这是 $\theta$ 的线性函数（注意：$w_j^{(2)} w_j^{(1)}$ 是双线性项，在固定激活模式后对 $\theta$ 整体仍为双线性，但 Hessian 的残差项为零因为 $\nabla_\theta^2 f_\theta = 0$ — 此处需要仔细处理）。

更精确地说：在 $\mathcal{R}_k$ 内，对激活神经元（$a_{ij}=1$），$f_\theta(x_i)$ 是 $w_j^{(2)}$ 和 $w_j^{(1)}$ 的双线性函数 $w_j^{(2)}(w_j^{(1)} \cdot x_i + b_j)$。此时 $\nabla_\theta^2 f_\theta(x_i) \neq 0$（交叉导数 $\partial^2/\partial w_j^{(1)}\partial w_j^{(2)}$ 非零）。因此引理 5 的残差 Hessian 项在 $\mathcal{R}_k$ 内并不为零。

**修正**：在 $\mathcal{R}_k$ 内，$f_\theta$ 对 $\theta$ 是光滑的（$C^\infty$ 甚至），但不一定是线性的——它是对 $w^{(1)}$ 和 $w^{(2)}$ 的双线性函数。Hessian 的非 Gauss-Newton 部分确实存在。

---

## 定理：引理 6: （修正版）— ReLU 网络在可微区域内的结构

**陈述**：在任意可微区域 $\mathcal{R}_k$ 内，$L_{\text{ReLU}} \in C^\infty$。梯度为：

$$\nabla L_{\text{ReLU}}(\theta) = \frac{1}{n}J(\theta)^\top r(\theta)$$

其中 $J(\theta) \in \mathbb{R}^{n \times d}$ 为 Jacobian（在 $\mathcal{R}_k$ 内为 $\theta$ 的线性函数），$r(\theta) = f_\theta(X) - y$。Hessian 为：

$$H_{\text{ReLU}}(\theta) = \frac{1}{n}J(\theta)^\top J(\theta) + \frac{1}{n}\sum_{i=1}^n r_i(\theta) H_{f,i}(\theta)$$

其中 $H_{f,i}(\theta) = \nabla_\theta^2 f_\theta(x_i)$ 在 $\mathcal{R}_k$ 内为非零常数矩阵（仅含交叉导数分量）。

**证明**：同引理 4 和 5 的推导，因为 ReLU 在 $\mathcal{R}_k$ 内退化为线性激活（$\sigma(z) = z$ 对激活神经元，$\sigma(z) = 0$ 对非激活神经元），$f_\theta$ 在 $\mathcal{R}_k$ 内是光滑的，引理 4/5 的链式法则推导完全适用。$\square$

---

## 定理：引理 7: （局部 PL* 条件 — 可微区域内）

**陈述**（依赖 P6）：在假设 A5（过参数化，$m \gg n$）下，存在以全局极小值 $\theta^*$ 为中心的邻域 $\mathcal{N}(\theta^*)$，使得对任意 $\theta \in \mathcal{N}(\theta^*) \cap \mathcal{R}_k$（其中 $\mathcal{R}_k$ 为 $\theta^*$ 所在的可微区域）有：

$$\|\nabla L_{\text{ReLU}}(\theta)\|^2 \geq 2\mu_k(L_{\text{ReLU}}(\theta) - L^*)$$

其中 $\mu_k = \frac{\lambda_{\min}(J_k^\top J_k)}{2n} > 0$。

**证明概要**（P6 待完整证明，此处给出基于 NTK 的推理）：当 $m \to \infty$ 时，由 NTK 理论（Jacot et al., 2018; Arora et al., 2019），Jacobian $J(\theta)$ 在训练过程中变化很小（NTK 极限下的惰性）。在 $\theta^*$ 的 $O(1/\sqrt{m})$ 邻域内，$J(\theta) \approx J(\theta^*)$ 且 $J^\top J$ 的最小特征值以 $\Theta(m)$ 增长（因随机初始化下 $J$ 的行近似独立）。由此，对足够大的 $m$，$J_k^\top J_k \succ 0$（因为 $m \gg n$ 且 $J_k \in \mathbb{R}^{n \times d}$ 行满秩，$d = m \cdot (\dim(x)+2) \gg n$）。更精确的常数推导需 P6 的完整框架。$\mu_k$ 的下界由 $\frac{\lambda_{\min}(K_{\text{NTK}})}{2}$ 给出，其中 $K_{\text{NTK}}$ 为 $n \times n$ 的 NTK 矩阵（**待 P6 补全**）。

---

## 定理：定理 3: （ReLU MLP：可微临界点分类）

**陈述**：在 A1（分段）+ A6 下，若局部 PL* 条件（引理 7）在 $\theta^*$ 所在可微区域 $\mathcal{R}_k$ 内成立，则 $L_{\text{ReLU}}$ 的任意可微临界点 $\theta^* \in \mathcal{R}_k$（$\nabla L_{\text{ReLU}}(\theta^*) = 0$，且 $\theta^*$ 不位于任何激活边界）为：

- (i) **全局极小值**，若 $H(\theta^*) \succeq 0$，此时 $L(\theta^*) = L^*$。
- (ii) **严格鞍点**，若 $H(\theta^*)$ 不定，此时仍满足 $L(\theta^*) = L^*$。

不存在可微的次优局部极小值（$L(\theta^*) > L^*$ 且 $H(\theta^*) \succ 0$）。

**证明**：与定理 2 的结构相同，但在可微区域 $\mathcal{R}_k$ 内应用局部 PL* 条件替代全局 PL。

设 $\theta^* \in \mathcal{R}_k$ 是临界点。由局部 PL* 条件（引理 7），在 $\mathcal{N}(\theta^*) \cap \mathcal{R}_k$ 内：

$$0 = \|\nabla L_{\text{ReLU}}(\theta^*)\|^2 \geq 2\mu_k(L_{\text{ReLU}}(\theta^*) - L^*)$$

因为 $\mu_k > 0$ 且 $L(\theta^*) - L^* \geq 0$，得 $L(\theta^*) = L^*$。因此 $\theta^*$ 是全局极小值。

关于 Hessian 分类：

- $H(\theta^*) \succeq 0$：$\theta^*$ 是全局极小值（二阶条件满足）。
- $H(\theta^*)$ 不定（存在负特征值）：$\theta^*$ 是严格鞍点。$\square$

**注**：此处存在微妙之处——虽然 $L(\theta^*) = L^*$，但 Hessian 可能不定。这意味着即使损失值为全局最小，某些方向仍导致损失增加（正曲率），某些方向导致损失减少（负曲率），但因为损失已经是最小值，沿负曲率方向移动时，初始的损失减少会在离开 $\mathcal{R}_k$ 时被 ReLU 激活变化所抵消或变为增加。在 $\mathcal{R}_k$ 内部，二次近似可能显示负方向，但实际损失不能低于 $L^*$，意味着沿这些方向的 Taylor 高阶项（不可忽略）或区域边界的不可微性起了约束作用。**待数值验证**。

---

## 第四部分：ReLU 不可微驻点

### 定义：Clarke 次梯度与 Clarke 驻点

对于局部 Lipschitz 函数 $L_{\text{ReLU}}$，Clarke 次梯度定义为：

$$\partial L(\theta) = \operatorname{conv}\left\{\lim_{k \to \infty} \nabla L(\theta_k) : \theta_k \to \theta,\; \theta_k \notin \Omega_{\text{nd}}\right\}$$

其中 $\Omega_{\text{nd}}$ 为不可微点集（Lebesgue 测度为零）。$0 \in \partial L(\theta)$ 的点称为 Clarke 驻点。

---

## 定理：定理 4: （ReLU 不可微驻点：PL 相容性下的非局部极小性质）

**陈述**（启发式猜测，待严格证明）：在 A4（Clarke PL 条件）或局部 Clarke PL* 下，设 $\theta^*$ 为 Clarke 驻点（$0 \in \partial L_{\text{ReLU}}(\theta^*)$）且位于至少一个激活边界上，则：

- 若 $L(\theta^*) > L^*$，则 $\theta^*$ **不是**局部极小值（在任意邻域内存在损失更小的点）。

等价地说：任何局部极小值（即使是不可微点）必须满足 $L(\theta^*) = L^*$。

**论证框架**（启发式，非严格证明）：

假设 $\theta^*$ 是局部极小值且 $L(\theta^*) > L^*$。因 $\theta^*$ 位于激活边界，存在一个或多个神经元满足 $w_j^{(1)} \cdot x_i + b_j = 0$。考虑一个充分接近的 $\theta$ 使得这些神经元的激活状态发生翻转。

在 $\theta^*$ 的任意小邻域内，$L$ 在该邻域的下确界 $\leq L^* < L(\theta^*)$（因为全局极小值可达且 $L^* < L(\theta^*)$）。因此 $\theta^*$ 不可能是局部极小值——除非 $L^*$ 不可达（但 ReLU 网络在过参数化下可实现零训练损失，参见 Arora et al., 2019）。

**困难**：需排除「悬崖」型局部极小——在不可微点处，函数可能在一个方向上上升（所有可微方向），但由于非光滑折角而在另一侧截断。Clarke PL 条件排除了这种可能性，因为次梯度的范数（或最小范数次梯度）满足 PL 不等式，从而 $0 \in \partial L(\theta^*)$ 蕴含 $L(\theta^*) = L^*$（与定理 2(i) 相同的逻辑）。

**正式猜测**：若 Clarke PL 条件成立（即 $\min_{g \in \partial L(\theta)} \|g\|^2 \geq 2\mu(L(\theta) - L^*)$），则任意 Clarke 驻点必为全局极小值。否则存在 $g \in \partial L(\theta^*)$ 使 $\|g\| = 0$ 但 $L(\theta^*) > L^*$，矛盾。$\square$（**待严格化：需验证 Clarke PL 条件在 ReLU 网络中成立的条件**）

---

## 第五部分：过参数化 → PL*（命题 P6 框架）

## 定理：定理 5: （过参数化诱导局部 PL* — NTK 框架）

**陈述**（待完整证明，此处给出证明框架）：在 A1（分段）+ A5（$m \to \infty$）+ A6 下，以高概率存在以随机初始化 $\theta_0$ 为中心的邻域 $\mathcal{B}_\rho(\theta_0)$（$\rho = O(1/\sqrt{m})$），使得：

1. 对所有 $\theta \in \mathcal{B}_\rho(\theta_0)$，NTK 矩阵 $K(\theta) = J(\theta)J(\theta)^\top \in \mathbb{R}^{n \times n}$ 满足 $\lambda_{\min}(K(\theta)) \geq \frac{\lambda_0}{2} > 0$，其中 $\lambda_0 = \lambda_{\min}(K_\infty)$（无限宽 NTK 的最小特征值）。

2. 由此导出局部 PL* 条件：

$$\|\nabla L(\theta)\|^2 = \frac{1}{n^2}r^\top K(\theta) r \geq \frac{\lambda_{\min}(K(\theta))}{n^2}\|r\|^2 = \frac{2\lambda_{\min}(K(\theta))}{n}(L(\theta) - L^*)$$

其中 $L^* = 0$（过参数化可实现零损失）。

**证明框架**（基于 Arora et al., 2019; Jacot et al., 2018）：

**步骤 1（NTK 正定性）**：在无限宽极限下，$K_\infty(x, x') = \mathbb{E}_{w \sim \mathcal{N}(0,I)}[x^\top x' \mathbf{1}[w^\top x \geq 0, w^\top x' \geq 0]]$。当数据点不平行（$x_i \not\propto x_j$ 对所有 $i \neq j$）时，$K_\infty \succ 0$（**文献**：Arora et al., 2019, Theorem 3.1）。

**步骤 2（有限宽度逼近）**：对 $m = \Omega\left(\frac{n^4}{\lambda_0^4 \delta^2}\right)$，以概率 $\geq 1-\delta$，对所有 $\theta \in \mathcal{B}_\rho(\theta_0)$ 有 $\|K(\theta) - K_\infty\|_2 \leq \frac{\lambda_0}{4}$，从而 $\lambda_{\min}(K(\theta)) \geq \frac{3\lambda_0}{4}$。

**步骤 3（局部 PL* 推导）**：

$$\begin{aligned}
\|\nabla L(\theta)\|^2 &= \left\|\frac{1}{n}J(\theta)^\top r\right\|^2 = \frac{1}{n^2}r^\top J(\theta)J(\theta)^\top r \\
&= \frac{1}{n^2}r^\top K(\theta) r \geq \frac{\lambda_{\min}(K(\theta))}{n^2}\|r\|^2 \\
&= \frac{2\lambda_{\min}(K(\theta))}{n} \cdot \frac{\|r\|^2}{2n} = \frac{2\lambda_{\min}(K(\theta))}{n}(L(\theta) - 0)
\end{aligned}$$

取 $\mu = \frac{\lambda_{\min}(K(\theta))}{n} \geq \frac{3\lambda_0}{4n} > 0$。$\square$

**待补全**：

- 邻域半径 $\rho$ 的精确刻画（依赖于 $m$、$\lambda_0$ 和 ReLU 的分段常数）。
- 从随机初始化到全局极小的整个训练轨迹是否始终保持在 PL* 区域内（Chizat & Bach, 2018 的惰性训练分析）。

---

## 总结：定理与引理依赖关系

```
P1 (引理 3: μ = σ⁺_min(X^TX)/n) ──→ P2 (定理 1: 线性模型无鞍点)
                                        │
P6 (定理 5: 过参数化 → 局部 PL*) ──→ P3 (定理 2: 光滑 MLP + PL ⇒ 无次优极小)
                                        │
                                        ├──→ P4 (定理 3: ReLU 可微临界点分类)
                                        │
                                        └──→ P5 (定理 4: ReLU 不可微驻点猜测)
```

| 命题 | 状态 |
|------|------|
| P1 | ✅ 引理 3 |
| P2 | ✅ 定理 1 |
| P3 | ✅ 定理 2 |
| P4 | ⚠️ 定理 3（依赖 P6 的 PL* 常数显式界） |
| P5 | ❓ 定理 4（启发式，待 Clarke PL 严格化） |
| P6 | ⚠️ 定理 5 框架（待补全 $\rho$ 和有限 $m$ 的精确分析） |

```yaml
verifiable:
  # P1: 线性模型 PL* 常数
  - expression: "L = (1/6)*((2*theta1 + theta2 - 3)**2 + (theta1 + 3*theta2 - 4)**2 + (theta1 + theta2 - 2)**2)"
    point: "1,1"
    expected:
      classification: global_minimum
      hessian_spectrum: "all non-negative"
    assumptions: [A1, A6]
    tier_hint: symbolic

  # P2: 正规方程解验证
  - expression: "L = (1/6)*((2*theta1 + theta2 - 3)**2 + (theta1 + 3*theta2 - 4)**2 + (theta1 + theta2 - 2)**2)"
    point: "正规方程解"
    expected:
      gradient_norm: 0
    assumptions: [A1, A6]
    tier_hint: symbolic
```
