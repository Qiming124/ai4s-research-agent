# 反例：ReLU 网络中的鞍点

## 失效假设

A1（全局 $C^2$）：ReLU 在零点不可二阶可微。

## 构造

二维参数 $\theta = (\theta_1, \theta_2)$，损失 $L(\theta) = \frac{1}{2}(\max(0, \theta_1) - y)^2 + \frac{1}{2}(\max(0, \theta_2) - y)^2$ 在 $\theta = 0$ 附近。

## 说明

临界点处 Hessian 可能为零矩阵或不存在经典二阶分类；需分段讨论或使用 Clarke 广义梯度。
