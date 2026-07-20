# PL条件下经验损失临界点分类

## 符号与假设
- **符号**：
  - $\theta \in \mathbb{R}^d$：参数向量
  - $X \in \mathbb{R}^{n \times d}$：设计矩阵
  - $y \in \mathbb{R}^n$：目标向量
  - $L_{\text{lin}}(\theta) = \frac{1}{2n}\|X\theta - y\|^2$：线性模型经验损失
  - $\sigma_{\min}^+(\cdot)$：最小正奇异值的平方（最小非零特征值）
  - $P_X = X(X^\top X)^+ X^\top$：到 $\operatorname{col}(X)$ 的正交投影
- **假设**：
  - A1 + A6：未标注
  - 其余假设未标注

## 引理

### 引理 1：线性模型的梯度与 Hessian
- **陈述**：对任意 $\theta \in \mathbb{R}^d$，
  $$\nabla L_{\text{lin}}(\theta) = \frac{1}{n}X^\top(X\theta - y),$$
  $$H_{\text{lin}}(\theta) = \frac{1}{n}X^\top X \quad \text{（常矩阵，不依赖于 } \theta \text{）}.$$
- **依赖假设**：未标注
- **证明要点**：
  1. 将 $L_{\text{lin}}(\theta)$ 展开为二次型：$\frac{1}{2n}(\theta^\top X^\top X\theta - 2y^\top X\theta + y^\top y)$。
  2. 对 $\theta$ 求一阶导得 $\frac{1}{n}(X^\top X\theta - X^\top y)$。
  3. 再求二阶导得常数矩阵 $\frac{1}{n}X^\top X$。
- **状态**：已证

### 引理 2：线性模型的临界点结构
- **陈述**：$\nabla L_{\text{lin}}(\theta^*) = 0$ 当且仅当 $X^\top X\theta^* = X^\top y$。所有临界点构成仿射子空间：
  $$\Theta^* = \{\theta^* : \theta^* = (X^\top X)^+ X^\top y + v,\; v \in \ker(X^\top X)\},$$
  且损失在该子空间上为常数 $L^*$。
- **依赖假设**：未标注
- **证明要点**：
  1. 由引理 1，梯度为零等价于正规方程。
  2. 当 $r = \operatorname{rank}(X) = d$ 时解唯一；当 $r < d$ 时解空间含齐次部分。
  3. 利用 $\ker(X^\top X) = \ker(X)$ 及伪逆给出通解形式。
  4. 损失恒定 $L^* = \frac{1}{2n}\|P_X y - y\|^2$，因 $X(\theta^*+v) = X\theta^*$。
- **状态**：已证

### 引理 3：线性模型的 PL* 常数
- **陈述**：在假设 A1 + A6 下，$L_{\text{lin}}$ 在任意临界点的邻域内满足 PL* 条件：
  $$\|\nabla L_{\text{lin}}(\theta)\|^2 \geq 2\mu (L_{\text{lin}}(\theta) - L^*),$$
  其中 $\mu = \frac{\sigma_{\min}^+(X^\top X)}{n} > 0$。
- **依赖假设**：A1, A6（具体内容未标注）
- **证明要点**：
  1. 令 $G = \frac{1}{n}X^\top X$，任取临界点 $\theta^*$ 满足 $G\theta^* = \frac{1}{n}X^\top y$，则 $\nabla L_{\text{lin}}(\theta) = G(\theta - \theta^*)$。
  2. 由 $G$ 谱分解，在 $\ker(G)^\perp$ 上有 $G \succeq \lambda_{\min}^+(G) I$，得 $\|\nabla L_{\text{lin}}\|^2 \ge \lambda_{\min}^+(G) (\theta - \theta^*)^\top G (\theta - \theta^*)$。
  3. 损失差为 $L_{\text{lin}}(\theta) - L^* = \frac{1}{2}(\theta - \theta^*)^\top G (\theta - \theta^*)$（二次函数 Taylor 精确）。
  4. 联立得 PL* 不等式，$\mu = \lambda_{\min}^+(G)$。因 $\theta$ 可任意取，结论对全局成立。
- **状态**：已证

## 定理
（草稿中未提供除引理外的独立定理陈述，故本节省略。）

## 开放问题
（草稿中未提供开放问题。）