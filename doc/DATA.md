# 数据目录约定（v2.2）

开发阶段本地 `data/` 会积累会话、向量库、Campaign 产物等。**纳入 Git 的只有种子与占位**；运行时产物已被 `.gitignore` 排除。

## 应保留的种子（版本库）

| 路径 | 说明 |
|------|------|
| `data/theory/symbols.md` 等 | 符号表、假设、矩阵、审稿清单、推导工作流 |
| `data/theory/campaigns/pl-critical-points.md` | Campaign 示范剧本 |
| `data/theory/counterexamples/relu_saddle.md` | 反例种子 |
| `data/theory/demo-quadratic-minimum.md` | 二次损失演示文稿 |
| `data/experiments/configs/*.yaml` | 实验配置（`quadratic_minimum`、`width_scaling`） |
| `data/**/.gitkeep` | 空目录占位 |

## 可随时删除的运行时数据（勿提交）

| 路径 | 说明 |
|------|------|
| `data/sessions.db` / `token_usage.db` | 会话与 Token 统计 |
| `data/chroma/` | RAG 向量库 |
| `data/campaigns/*` | Campaign 阶段 JSON / report（保留 `.gitkeep`） |
| `data/explore_outputs/*` | SkillsBridge / 探索输出 |
| `data/experiments/logs/*` | 实验运行日志 |
| `data/experiments/notebooks/results/` | Jupyter 回传结果 |
| `data/quant_probe/` | API 量化探针 JSONL/汇总（live RTT；勿提交） |
| `data/projects/*` | 课题运行时工作区 |
| `data/theory/smoke_test_file.md`、`*-problem.md` | 冒烟/流水线临时稿 |
| `data/theory/counterexamples/*`（除 `relu_saddle.md`） | 自动生成的反例 |

清理示例（开发机）：

```bash
rm -f data/sessions.db data/token_usage.db data/theory/smoke_test_file.md
rm -rf data/chroma/* data/campaigns/*/ data/explore_outputs/*.json \
  data/experiments/logs/*.json data/experiments/notebooks/results/*
find data/projects -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} +
```

## 双 `.env` 注意

加载优先 **`conf/.env`**。若根目录另有 `.env`，勿依赖其覆盖服务端配置，以免与 `conf/.env` 漂移。
