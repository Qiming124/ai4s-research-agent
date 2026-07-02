# 全局符号表

本项目推导与实验统一使用以下符号。

| 符号 | 含义 |
|------|------|
| $L(\theta)$ | 损失函数，$\theta$ 为模型参数 |
| $\theta \in \mathbb{R}^d$ | 参数向量，$d$ 为参数维度 |
| $\nabla L(\theta)$ | 梯度向量 |
| $H(\theta) = \nabla^2 L(\theta)$ | Hessian 矩阵 |
| $\lambda_{\min}(H)$ | Hessian 最小特征值 |
| $\theta^*$ | 临界点（$\nabla L(\theta^*) = 0$） |
| 局部极小 | $\nabla L(\theta^*)=0$ 且 $H(\theta^*) \succ 0$ |
| 鞍点 | $\nabla L(\theta^*)=0$ 且 $H(\theta^*)$ 不定（存在正负特征值） |
| PL 条件 | $\|\nabla L(\theta)\|^2 \geq 2\mu(L(\theta) - L^*)$ |
| $\mu$ | PL 常数或强凸常数 |
| $\delta$ | Huber 损失阈值等辅助参数 |

## 记号约定

- 向量范数 $\|\cdot\|$ 默认为 $\ell_2$ 范数
- 矩阵正定记为 $A \succ 0$，半正定 $A \succeq 0$
- 「局部」指存在邻域 $B_\varepsilon(\theta^*)$ 内成立
