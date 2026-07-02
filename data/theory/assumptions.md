# 全局假设

推导时须显式声明使用了哪些假设；未声明则默认不成立。

## A1 光滑性

损失 $L$ 在考虑的参数域上 $C^2$（二阶连续可微）。

## A2 有界域

参数限制在紧集 $\Theta \subset \mathbb{R}^d$ 内优化。

## A3 强凸（充分条件）

存在 $\mu > 0$ 使得 $\nabla^2 L(\theta) \succeq \mu I$ 对所有 $\theta \in \Theta$。  
推论：任意局部极小点为全局极小点。

## A4 PL 条件

存在 $\mu > 0$ 满足 Polyak-Łojasiewicz 不等式（见 symbols.md）。

## A5 过参数化

网络宽度 $m \to \infty$ 时，训练集上损失可趋近于零；landscape 结构发生变化。

## A6 有限样本

训练集固定为 $\{(x_i, y_i)\}_{i=1}^n$，经验风险 $L(\theta) = \frac{1}{n}\sum_i \ell(f_\theta(x_i), y_i)$。

## 使用说明

- 每条定理须列出依赖的假设编号（如 A1, A3）
- 反例须指明失效的假设（见 `counterexamples/`）
