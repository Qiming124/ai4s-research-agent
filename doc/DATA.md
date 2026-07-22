# 数据目录约定（v2.2）

开发阶段本地 `data/` 会积累会话、向量库、工件等。**纳入 Git 的只有种子与占位**；运行时产物已被 `.gitignore` 排除。

> Campaign 运行时目录 `data/campaigns/` 已废弃（代码不再读写）；本地若仍有空占位可忽略或删除。

## 应保留的种子（版本库）

| 路径 | 说明 |
|------|------|
| `data/theory/symbols.md` 等 | 符号表、假设、矩阵、审稿清单（**只读种子**；运行时复制到课题工作区） |
| `data/theory/campaigns/pl-critical-points.md` | 局部极小 / PL 课题示范剧本（历史文件名保留） |
| `data/theory/counterexamples/relu_saddle.md` | 反例种子 |
| `data/theory/demo-quadratic-minimum.md` | 二次损失演示文稿 |
| `data/experiments/configs/*.yaml` | 实验配置（`quadratic_minimum`、`width_scaling`） |
| `data/**/.gitkeep` | 空目录占位 |

## 课题隔离运行时目录

```
data/projects/{project_id}/
  theory/          # 该课题理论工作区（symbols / assumptions / lemmas…）
  experiments/     # 课题级实验产物（可选）
```

RAG 向量仍在 `data/chroma/`，元数据带 `project_id`（课题共享语料）；`session_rag_refs` 仍按会话记录引用轨迹。  
策展文献语料见 [`../data/arxiv_refs/LIBRARY.md`](../data/arxiv_refs/LIBRARY.md)（会话 `ai4s-library` · 课题 `default`）。  
理论侧 Artifact 默认落在会话/课题相关存储（见 `server/artifacts/`），**不以** `data/campaigns/` 为路径。

## 可随时删除的运行时数据（勿提交）

| 路径 | 说明 |
|------|------|
| `data/sessions.db` / `token_usage.db` | 会话与 Token 统计 |
| `data/chroma/` | RAG 向量库 |
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
rm -rf data/chroma/* data/explore_outputs/*.json \
  data/experiments/logs/*.json data/experiments/notebooks/results/*
# 若仍有旧 Campaign 空目录：
rm -rf data/campaigns
find data/projects -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} +
```

SQLite 旧表：代码已不再创建 `research_campaigns`；若本地库仍残留可执行  
`DROP TABLE IF EXISTS research_campaigns;`（`bibliography` 表可保留，供 LaTeX 导出内部使用）。

## 双 `.env` 注意

加载优先 **`conf/.env`**。若根目录另有 `.env`，勿依赖其覆盖服务端配置，以免与 `conf/.env` 漂移。
