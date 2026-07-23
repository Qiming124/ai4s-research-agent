# 数据目录约定

开发阶段本地 `data/` 会积累会话、向量库、工件等。**纳入 Git 的只有种子与占位**；运行时产物已被 `.gitignore` 排除。

> Campaign 运行时目录 `data/campaigns/` 已废弃（代码不再读写）；本地若仍有空占位可忽略或删除。

## 应保留的种子（版本库）

| 路径 | 说明 |
|------|------|
| `data/theory/symbols.md` 等 | **历史参考**种子（符号表、假设、矩阵、审稿清单）；**不再**自动复制到新课题，**不再**注入 system prompt |
| `data/theory/campaigns/pl-critical-points.md` | 局部极小 / PL 课题示范剧本（历史文件名保留） |
| `data/theory/counterexamples/relu_saddle.md` | 反例种子 |
| `data/theory/demo-quadratic-minimum.md` | 二次损失演示文稿 |
| `data/experiments/configs/*.yaml` | 实验配置（`quadratic_minimum`、`width_scaling`） |
| `data/**/.gitkeep` | 空目录占位 |

## 课题隔离运行时目录

```
data/projects/{project_id}/
  theory/          # 空目录占位（.gitkeep）；假设请写入 L4，勿依赖 A1–A6 模板
  experiments/     # 课题级实验产物（日志 / 上传表）；filesystem MCP 仅允许此子树
  experiments/logs/
```

RAG 向量仍在 `data/chroma/`，元数据带 `project_id`（课题共享语料）；`session_rag_refs` 仍按会话记录引用轨迹。  
聊天请求若带 `project_id`，服务端会自动 `link_session`，避免会话落在 `default` 导致 RAG/工件串题。  
策展文献语料见 [`../data/arxiv_refs/LIBRARY.md`](../data/arxiv_refs/LIBRARY.md)（会话 `ai4s-library` · 课题 `default`）。  
理论侧 Artifact 默认落在会话/课题相关存储（见 `server/artifacts/`），**不以** `data/campaigns/` 为路径。

**MCP filesystem**：默认允许 `data/mcp_files` 与 `data/projects/*/experiments`；禁止 `data/theory` 与课题 `theory/` 下已下线 md。

## 可随时删除的运行时数据（勿提交）

| 路径 | 说明 |
|------|------|
| `data/sessions.db` / `token_usage.db` | 会话与 Token 统计 |
| `data/chroma/` | RAG 向量库 |
| `data/explore_outputs/*` | SkillsBridge / 探索输出 |
| `data/experiments/logs/*` | 实验运行日志 |
| `data/experiments/notebooks/results/` | Jupyter 回传结果 |
| `data/quant_probe/` | 本地探针输出占位（探针脚本已移除；目录可空） |
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
