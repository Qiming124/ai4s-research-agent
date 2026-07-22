# AI4S 文献语料目录（RAG）

会话：`ai4s-library` · 课题：`default`  
用途：理论侧多智能体检索用的**策展语料**（非测试残留）。  
重建：清空 `DELETE /v1/documents?purge=true` 后按本表重新入库。

## 本地 PDF（`data/arxiv_refs/`）

| arXiv | 标题（简述） | 主题 |
|-------|--------------|------|
| 1406.2572 | Identifying and attacking the saddle point problem | DL 优化 / 鞍点 |
| 1608.04636 | Linear Convergence under the PL Condition | PL / 优化理论 |
| 2003.00307 | Loss landscapes in over-parameterized systems | 损失景观 / 过参数化 |

## 经 API 入库的 arXiv

| arXiv | 标题（简述） | 主题 |
|-------|--------------|------|
| 1711.10561 | Physics Informed Deep Learning (PINNs) | **AI4S / SciML** |
| 2408.16806 | PINNs and Extensions (review) | **AI4S** |
| 1605.07110 | Deep Learning without Poor Local Minima | DL 优化理论（示范子集） |
| 1412.0233 | The Loss Surfaces of Multilayer Networks | 损失景观（示范子集） |
| 1806.07366 | Neural Ordinary Differential Equations | 连续深度模型 / 科学建模 |
| 2006.11239 | Denoising Diffusion Probabilistic Models | 生成模型（科学仿真管线相关） |

## 说明

- 已从 RAG **清除**：量化探针会话、smoke_test、`*-problem.md`、重复的理论工作区 md、旧 Campaign 反例稿等测试/噪声索引。
- 课题工作区 `symbols.md` / `assumptions.md` 仍由理论注入路径使用，**不**再整包塞进 RAG。
- `FORMAT_NOTES.txt` 仅为排版备注，不入库。
