# 开发辅助工具清单

面向「深度学习损失函数局部极小值理论推导 + Agent 工作流」开发的 MCP、Skills、Rules 与本地工具推荐。

> 生成日期：2026-06-29  
> 适用项目：AI4S 科研辅助 Agent（`agent/`）  
> 用法：按优先级勾选安装；Cursor 侧与项目服务端侧分开配置。

---

## 一、当前已具备能力

### 1.1 项目内置 MCP Server（`conf/mcp_servers.json`）

| Server | 工具 | 状态 | 主要用途 |
|--------|------|------|----------|
| `web_search` | `web_search__search` | ✅ 已启用 | DuckDuckGo / Wikipedia 检索 |
| `arxiv` | `arxiv__search_papers`、`arxiv__get_paper` | ✅ 已启用 | 论文搜索与元数据 |
| `filesystem` | `read_file`、`write_file`、`list_files` | ✅ 已启用 | `MCP_ALLOWED_DIRS` 内文件读写 |
| `sympy` | `simplify_expression`、`differentiate`、`solve_equation` 等 | ✅ 已配置 | 符号化简、求导、求解 |

配置说明见 [mcp-config.md](mcp-config.md)。

### 1.2 项目 Agent 路由（LangGraph / legacy）

| Agent | 职责 | 当前 MCP 白名单（`conf/mcp_tool_whitelist.json`） |
|-------|------|-----------------------------------------------------|
| `literature` | 文献检索 | `arxiv__*`、`web_search__*` |
| `theory` | 数学推导 | `__none__`（待开放 sympy） |
| `experiment` | 实验分析 | `filesystem__*` |
| `general` | 通用对话 | `*` |

> **待办**：将 `theory` 白名单改为 `sympy__*`，使推导 Agent 能调用符号计算而不误用搜索工具。

### 1.3 Cursor IDE 已启用 MCP

| MCP Server | 用途 |
|------------|------|
| cursor-ide-browser | 浏览器自动化、截图、页面调试 |
| GitKraken / GitLens | Git 操作 |
| Firecrawl | 网页抓取 |
| Fetch | URL 内容拉取 |
| 百度搜索 | 中文检索 |
| Excel | Excel 读写 |

### 1.4 Cursor 已安装 Skills

| Skill | 路径关键词 | 对你工作的价值 |
|-------|------------|----------------|
| brainstorming | 创意/功能前澄清需求 | ⭐⭐⭐ 设计 agent 阶段与假设 |
| canvas | 交互式分析页 | ⭐⭐⭐ 损失曲面、优化轨迹可视化 |
| sdk | Cursor SDK 自动化 | ⭐⭐⭐ 编排多 agent、CI 集成 |
| create-rule | 写 `.cursor/rules` | ⭐⭐⭐ 推导纪律、符号规范 |
| create-skill | 写自定义 skill | ⭐⭐⭐ 固化 theory 工作流 |
| review-bugbot | 代码审查 | ⭐⭐ 改 agent / MCP 代码时 |
| review-security | 安全审查 | ⭐⭐ 部署与 MCP 命令注入风险 |
| frontend-design | UI 设计 | ⭐ Web 三栏界面优化 |
| find-skills | 发现新 skill | ⭐ 扩展能力时检索 |
| skill-creator | skill 评测优化 | ⭐ 迭代自定义 skill |
| automate / create-hook / loop | 自动化与钩子 | ⭐ 保存推导稿时触发检查 |
| babysit / split-to-prs | PR 维护与拆分 | ⭐ 协作开发时 |
| canvas-design | 静态视觉设计 | ⭐ 论文级示意图 |
| update-cursor-settings | 编辑器设置 | 按需 |
| statusline | CLI 状态栏 | 按需 |

---

## 二、推荐补充清单（按优先级）

### P0 — 立即做（性价比最高）

- [ ] **开放 theory Agent 的 SymPy 白名单**

  编辑 `conf/mcp_tool_whitelist.json`：

  ```json
  "theory": ["sympy__*"]
  ```

  重启 uvicorn 后，用 `mode=math` 或路由到 theory 的请求验证工具调用。

- [ ] **自建 Cursor Skill：`loss-landscape-workflow`**

  固化多阶段工作流：

  1. 问题形式化（损失、参数空间、临界点定义）
  2. 局部条件（∇L=0，Hessian 定性）
  3. 全局/概率陈述（过参数化、隐式偏置等）
  4. SymPy 检查 + 低维数值例子
  5. 审稿清单（符号一致、假设完整、反例）

- [ ] **自建 Cursor Rule：理论推导规范**

  建议写入 `.cursor/rules/theory-derivation.mdc`，内容包括：

  - 全局符号表（L, θ, λ_min(H) 等）
  - 禁止未证明的「显然」「易得」
  - 每定理附假设列表与维度说明
  - 引用格式：`[引理编号] + arXiv ID 或自证`

- [ ] **理论目录结构**（便于 agent 与人类共用）

  ```
  data/theory/
  ├── symbols.md          # 符号表
  ├── assumptions.md      # 全局假设
  ├── lemmas/             # 分引理 Markdown / TeX
  ├── proofs/             # 完整证明稿
  └── review-checklist.md # 人工审稿清单
  ```

  将 `data/theory/` 加入 `MCP_ALLOWED_DIRS`，供 filesystem MCP 读写。

---

### P1 — 近期安装（文献 + 验证闭环）

#### 项目服务端 MCP（自研优先，见 mcp-config.md）

- [ ] **SymPy 扩展工具**（在现有 `sympy.py` 上追加）

  | 建议工具名 | 功能 |
  |------------|------|
  | `hessian_eigenvalues` | 给定表达式与变量，返回 Hessian 及特征值符号判断 |
  | `taylor_expand` | 临界点邻域泰勒展开 |
  | `substitute_and_simplify` | 代入假设后化简（减少 LLM 手算错误） |

- [ ] **Tavily 搜索**（可选，需 API Key）

  ```json
  "tavily": {
    "command": "npx",
    "args": ["-y", "@anthropic/mcp-server-tavily"],
    "env": { "TAVILY_API_KEY": "${TAVILY_API_KEY}" },
    "enabled": false
  }
  ```

  在 `.env` 配置 `TAVILY_API_KEY`；`literature` Agent 白名单增加 `tavily__*`。

- [ ] **RAG 文献库**（项目已规划 Phase 3）

  - 将精读 PDF / 笔记 ingest 到 Chroma（`POST /v1/documents`）
  - `literature` / `theory` Agent 增加 `rag_retrieve` 工具（实现后）

#### Cursor IDE MCP（个人开发环境）

- [ ] **arXiv / Semantic Scholar MCP**（社区包，按可用性选装）

  用途：在 Cursor 里直接查论文，与项目内置 `arxiv` Server 互补（IDE 写代码时用）。

- [ ] **Zotero**（本地 + 可选 MCP）

  用途：PDF 管理、BibTeX 导出、阅读笔记；理论工作长期必备。

#### 本地 Python 工具（不必 MCP，notebook / 脚本即可）

- [ ] **SymPy** — `pip install sympy`（项目 MCP 已依赖）
- [ ] **NumPy / SciPy** — 随机 Hessian、特征值数值验证
- [ ] **PyTorch 或 JAX** — 小网络 loss landscape 实验
- [ ] **Matplotlib / Plotly** — 2D contour、优化轨迹图

#### Cursor Skills

- [ ] **`derivation-verify` skill**（自建）

  模板：定义损失 → SymPy 求 ∇L、∇²L → d=2,5 随机数值扫临界点类型。

- [ ] **`paper-review` skill**（自建）

  强制每步标注文献来源或「自证」；检索 arxiv 后再写综述段落。

---

### P2 — 中期增强（写作 + 实验 + 编排）

#### 学术写作

- [ ] **LaTeX 本地环境**：`texlive` + `latexmk`
- [ ] **Pandoc**：Markdown 推导稿 ↔ LaTeX（可选 MCP）
- [ ] **KaTeX 公式**：Web 端已支持；理论稿保持 `$...$` / `$$...$$` 一致

#### 实验记录

- [ ] **Weights & Biases** 或 **MLflow**

  记录：不同初始化、宽度、学习率下的 loss / Hessian 谱实验。

- [ ] **Jupyter Lab**

  `data/experiments/notebooks/` 下放可复现 notebook；`experiment` Agent 通过 filesystem 读取日志。

#### Agent 编排

- [ ] **LangGraph 子图细化**（`ORCHESTRATION_BACKEND=langgraph`）

  theory → verify（sympy）→ review（checklist）闭环。

- [ ] **Cursor SDK 脚本**（`sdk` skill）

  自动化：批量跑推导 case、回归测试 MCP 工具输出。

- [ ] **Cursor Hooks**（`create-hook` skill）

  保存 `data/theory/proofs/*.md` 时触发符号表一致性检查。

#### Cursor IDE MCP（可选）

- [ ] **Wolfram Alpha MCP** — 快速查特殊函数、矩阵性质（需 API）
- [ ] **GitHub MCP** — Issue/PR 与文献 issue 跟踪（若用 gh 流程）

---

### P3 — 进阶（严格形式化，非必需）

- [ ] **Lean 4** — 分析/代数结构可形式化时
- [ ] **Isabelle / Coq** — 测度论、概率陈述严格化
- [ ] **形式化验证 MCP** — 仅当核心引理稳定后再投入

> 建议路径：LLM 草稿 → SymPy → 数值实验 → 稳定后再考虑 Lean。

---

## 三、不建议优先安装

| 类型 | 原因 |
|------|------|
| 更多通用搜索 MCP | 已有 web_search、Fetch、Firecrawl、百度 |
| 重型数据库 MCP | 除非推导 DAG 规模很大 |
| 过多 Browser 自动化 | 论文站用 arxiv API / Fetch 更稳定 |
| 与 React 强绑定的全局规则 | 当前主线是 ML 理论 + Agent；可单独加 theory 规则，不必扩展现有 Web 规范 |

---

## 四、Cursor MCP 安装参考命令

> 在 Cursor：**Settings → MCP → Add new MCP server**。以下为常见社区包示例，安装前请确认来源可信。

```json
// ~/.cursor/mcp.json 示例片段（按实际路径调整）

{
  "mcpServers": {
    "arxiv": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-arxiv"]
    },
    "tavily": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-tavily"],
      "env": { "TAVILY_API_KEY": "your-key" }
    }
  }
}
```

Python 类 MCP 也可用 `uvx` / `python -m` 启动，与项目 `mcp_servers.json` 写法一致。

---

## 五、项目 MCP 快速验收

```bash
# 1. 启用 MCP
# conf/.env: ENABLE_MCP=true

# 2. 重启 API
# uvicorn ... --app-dir app

# 3. 查看状态
curl http://127.0.0.1:8000/v1/mcp/status

# 4. 跑测试
pytest tests/test_mcp.py tests/test_whitelist.py -v
```

---

## 六、推荐自建 Skill 大纲（复制后改写）

### 6.1 `loss-landscape-workflow`

```markdown
---
name: loss-landscape-workflow
description: 深度学习损失函数局部极小值理论推导的多阶段 agent 工作流。
---

## 阶段
1. 形式化：写出 L(θ)、参数域、临界点/鞍点/极小点定义
2. 局部分析：一阶必要条件、二阶充分/必要条件
3. 结构假设：过参数化、NTK、隐式偏置等（写明适用条件）
4. 验证：SymPy 化简 + d≤5 数值 Hessian
5. 审稿：符号表、维度、反例、文献引用

## 输出格式
- 引理 / 定理 / 证明 分节
- 每步等式变换注明依据（代数 / 引理 X / 文献）
```

### 6.2 `derivation-verify`

```markdown
---
name: derivation-verify
description: 用 SymPy 与数值实验验证 LLM 推导稿。
---

## 步骤
1. 从文稿提取 L(θ) 与变量
2. 调用 sympy MCP：simplify / differentiate / solve
3. 在 θ∈R^2 网格上算 ∇L、特征值符号
4. 输出：通过 / 失败 + 反例点
```

---

## 七、总览检查表（可打印）

| 类别 | 项目 | 优先级 | 完成 |
|------|------|--------|------|
| 项目 MCP | theory 开放 sympy 白名单 | P0 | ☐ |
| 项目 MCP | SymPy Hessian / 泰勒工具 | P1 | ☐ |
| 项目 MCP | Tavily 搜索（可选） | P1 | ☐ |
| 项目 MCP | RAG 文献检索 | P1 | ☐ |
| 目录 | `data/theory/` 结构 | P0 | ☐ |
| Cursor Skill | loss-landscape-workflow | P0 | ☐ |
| Cursor Skill | derivation-verify | P1 | ☐ |
| Cursor Skill | paper-review | P1 | ☐ |
| Cursor Rule | theory-derivation 规范 | P0 | ☐ |
| 本地工具 | PyTorch/JAX + Matplotlib | P1 | ☐ |
| 本地工具 | LaTeX + latexmk | P2 | ☐ |
| 实验 | W&B 或 MLflow | P2 | ☐ |
| 编排 | LangGraph theory 验证闭环 | P2 | ☐ |
| 进阶 | Lean / 形式化 | P3 | ☐ |

---

## 八、相关文档

| 文档 | 说明 |
|------|------|
| [mcp-config.md](mcp-config.md) | 项目 MCP 配置与扩展 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 多 Agent 与 LangGraph |
| [ENV.md](ENV.md) | 环境变量 |
| [../README.md](../README.md) | 项目总览 |

---

*本文档随项目演进更新；安装第三方 MCP 前请审查命令来源与 API Key 权限。*
