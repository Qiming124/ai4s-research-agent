# 言晖科研助手（v2.2）

面向「**用深度学习解决科学问题**」的 **理论侧多智能体系统**：帮你检索与阅读文献、总结证明方法、做理论形式化推导、设计实验计划，并解读你上传的实验数据。

> **一句话定位**：这是「科研顾问」，不是「代跑训练平台」。系统帮你想清楚理论与实验该怎么做；**真正的训练与大规模数值实验仍在你自己的环境里完成**。

| | |
|--|--|
| **示范课题** | 损失函数局部极小 / 优化理论等（能力子集，不是唯一领域） |
| **明确不做** | 在系统内代跑大规模训练、部署模型、复现完整实验流水线 |
| **详细蓝图** | [`doc/PRODUCT-VISION.md`](doc/PRODUCT-VISION.md) |
| **其它文档** | [`doc/README.md`](doc/README.md) · [`doc/ENV.md`](doc/ENV.md) · [`doc/API-ROUTES.md`](doc/API-ROUTES.md) · [`doc/KNOWN_ISSUES.md`](doc/KNOWN_ISSUES.md) |

---

## 目录

1. [系统组成](#1-系统组成一目了然)
2. [理论侧工作流程](#2-理论侧工作流程新人必读)
3. [核心能力说明](#3-核心能力说明sse--思维链--子-agent--rag--mcp)
4. [子 Agent 角色定位](#4-子-agent-角色定位)
5. [MCP 工具说明](#5-mcp-工具说明)
6. [底层 LLM 与关键参数](#6-底层-llm-与关键参数)
7. [前端 Web 可调用功能与执行流程](#7-前端-web-可调用功能与执行流程)
8. [示例项目执行案例](#8-示例项目执行案例)
9. [快速启动与目录结构](#9-快速启动与目录结构)
10. [常见问题与扩展](#10-常见问题与扩展)

---

## 1. 系统组成（一目了然）

把系统想成一支「理论侧科研小分队」，外加若干工具箱：

```
┌──────────────────────────────────────────────────────────────┐
│  Web 工作台（React）                                          │
│  左栏：课题 + 会话    中间：对话（SSE 流式）    右栏：文献/理论/产出 │
└────────────────────────────┬─────────────────────────────────┘
                             │ HTTP + SSE
┌────────────────────────────▼─────────────────────────────────┐
│  编排层（Agent 系统）                                          │
│  general 协调路由 → literature / theory / review /            │
│  counterexample / experiment 等专责子 Agent                    │
└──────────────┬─────────────────────────────┬─────────────────┘
               │                             │
     ┌─────────▼─────────┐         ┌─────────▼─────────┐
     │ 记忆层             │         │ 工具层（MCP）       │
     │ · L1 工作记忆      │         │ · arXiv / 网页搜索  │
     │ · L2 会话持久化    │         │ · SymPy 符号核对    │
     │ · L3 RAG 向量库    │         │ · 文件系统（受限）  │
     │ · L4 定理库        │         │ · numerical（可选） │
     │ · 课题 / 工件      │         │                     │
     └─────────┬─────────┘         └─────────┬─────────┘
               │                             │
               └──────────────┬──────────────┘
                              ▼
                    底层大模型 DeepSeek
                 （流式推理 reasoning + 正文）
```

| 层级 | 做什么 | 你在界面上哪里能感到它 |
|------|--------|------------------------|
| **Web 工作台** | 发消息、管课题/会话、上传文献与实验数据、看推导迹与实验计划 | 整页 UI |
| **Agent 编排** | 决定「该谁回答」、调用哪些工具、是否切换角色 | 顶栏当前 Agent、消息下的工作流时间线 |
| **记忆** | L1 截断/摘要、L2 会话存档、L3 RAG、L4 定理库 | 切换会话仍在、文献引用、「理论」定理库 |
| **MCP 工具** | 让 Agent 能搜论文、算符号、读允许目录里的文件 | 时间线里的「工具调用」节点 |
| **LLM** | 真正写证明、写计划、做解读的「大脑」 | 思维链面板 + 流式正文 |

---

## 2. 理论侧工作流程（新人必读）

下面按「做一篇理论向课题」的自然顺序说明。不必每一步都走完；可按需要跳步或回环。

### 总览图

```
① 文献检索          在公开渠道找到相关论文（标题/摘要/链接）
        ↓
② 文献入库与阅读    把 PDF 等放进课题；系统切成片段供检索（RAG）
        ↓
③ 证明 / 方法总结   提炼：问题设定、关键假设、关键步骤、公式骨架
        ↓
④ 理论证明与形式化  用统一符号写出定义→引理→定理；可符号核对
        ↓
⑤ （可选）审稿 / 反例  查严谨性缺口；或构造最小反例检验边界
        ↓
⑥ 实验计划设计      说明要测什么、对照是什么、成功判据、记哪些字段
        ↓
⑦ 实验数据上传      你在自己环境跑完实验后，经「产出→回传结果」交回
        ↓
⑧ 结果分析与下一步  对照理论：支持 / 反驳 / 不确定；列出缺数与下一组实验
        ↺ 必要时回到 ③ 或 ④ 修订主张
```

### 各阶段详细说明

#### ① 文献检索

- **目的**：搞清楚领域里「别人怎么证明 / 怎么建模」。
- **谁来做**：通常交给 **literature** Agent。
- **做什么**：按关键词搜 arXiv、必要时补公开网页；整理标题、作者、年份、贡献摘要。
- **注意**：这一步拿到的是**外部**文献线索，还不等于系统已经「读过你本地的 PDF」。

#### ② 文献入库与阅读

- **目的**：让后续推导能引用**你课题里的原文片段**，而不是凭空编造。
- **你做什么**：在右栏「文献」上传 PDF/DOCX/Markdown，或从 arXiv ID 导入。
- **系统做什么**：切块、向量化，写入 RAG（按会话/课题隔离）。之后 **theory** 等可用 `rag__retrieve` 检索相关段落。
- **新人易混点**：literature **不能**直接读已上传 PDF（无 RAG 权限）；读库内文献请切 **theory**（或 general）。

#### ③ 证明方法总结

- **目的**：把长论文压成「可复述的方法要点」，方便形式化。
- **产出形态**：问题设定、关键量/损失形式、关键假设、证明或算法步骤摘要、公式骨架（LaTeX）、与当前课题的关系。
- **谁来做**：literature 可基于摘要做提炼；已入库后 theory 可结合 RAG 片段写得更贴原文。

#### ④ 理论证明与形式化

- **目的**：把科学主张写成可检查的数学结构（定义 / 引理 / 定理 / 边界条件）。
- **谁来做**：**theory**（主路径）。
- **辅助**：SymPy 做化简、求导、凸性等**轻量符号核对**；可选网页补充背景。
- **界面产物**：回答末尾可落盘 **推导迹（DerivationTrace）**，出现在右栏「理论」；重要结论可写入 **定理库（L4）**。

#### ⑤ （可选）审稿与反例

- **review**：不调用工具，只基于对话与定理库检查符号一致性、假设是否齐全、证明有无缺口；给出通过 / 小修 / 大修级意见。
- **counterexample**：针对可疑猜想构造**最小**反例思路，说明哪个假设失效；可用 SymPy 核对表达式。

#### ⑥ 实验计划设计

- **目的**：回答「为了检验这个理论主张，我该做怎样的实验？」
- **谁来做**：**experiment**（实验顾问）。
- **计划应包含**：目标主张、自变量与对照、记录字段、成功/失败判据、注意事项。
- **界面产物**：**实验计划（ExperimentPlan）** 写入「产出」面板。  
- **重要**：计划由你在**自己的**训练/仿真环境执行；本系统不代跑大规模训练。

#### ⑦ 实验数据上传

- **正确做法**：打开「产出」→ **「回传结果」**，上传 Excel / CSV / JSON，或填写 summary + metrics。
- **错误做法**：不要手工把文件拷到 `data/projects/.../experiments/` 当「回传」。
- **系统写入**：实验记录 + **DataPacket** 工件，供下一轮解读。

#### ⑧ 结果分析与下一步

- **谁来做**：仍由 **experiment** 读回传数据，对照理论主张给出：支持 / 反驳 / 不确定、缺数字段、下一组实验建议（可再落盘 NextStepMemo / 修订计划）。
- **回环**：若数据推翻假设，回到 theory 收紧条件，或再补文献。

---

## 3. 核心能力说明（SSE · 思维链 · 子 Agent · RAG · MCP）

### 3.1 SSE 流式对话

前端通过 **Server-Sent Events** 接收回答，而不是等整段生成完才显示。

一次典型流大致顺序：

| 事件类型（概念） | 你看到什么 |
|------------------|------------|
| `meta` | 本次用了哪个 Agent、路由原因等 |
| `workflow_step` / 工具相关事件 | 工作流时间线：规划 → 调工具 → 综合 |
| `reasoning` | 模型「边想边写」的推理过程（可开关） |
| `content` | 用户可见的正文（Markdown / LaTeX） |
| `artifact_saved` | 推导迹、实验计划等工件已保存 |
| `done` | 本轮结束 |

好处：长证明、多轮工具调用时，界面能实时刷新，并可中途停止生成。

### 3.2 思维链（Reasoning / CoT）

- **Reasoning**：DeepSeek 的推理通道内容，前端可在思维链面板展示（设置里可关）。
- **CoT 分步**：部分模式下会把回答解析成「步骤标题 + 正文」，便于跟证明节奏。
- **和「工具调用」的区别**：思维链是模型内部推理文本；工具调用是真实执行了 arXiv / SymPy 等外部动作。

### 3.3 子 Agent 与路由

系统不是单一聊天机器人，而是 **多角色**：

- 可在侧栏 **手动指定** Agent；
- 或开启 **自动路由**（关键词规则；可选再用 LLM 分类，失败回退规则）。

推荐闭环：

`literature` →（入库）→ `theory` →（可选 `review` / `counterexample`）→ `experiment`（计划 ↔ 回传读数）

含糊问题可先用 `general` 拆解，再切换专责角色。

### 3.4 RAG（检索增强）

- **是什么**：把你上传的文献切成小段，存进向量库；提问时检索最相关的几段，塞进模型上下文。
- **解决什么问题**：减少「瞎编论文内容」；让证明能对齐你课题里的原文表述。
- **谁会用**：白名单允许的 Agent（常见为 theory / experiment / general）；**literature 不用 RAG**。
- **前提**：必须先在「文献」Tab 入库；空库检索会没有结果。

### 3.5 MCP（工具协议）

- **是什么**：Model Context Protocol——把「搜论文」「符号计算」等能力注册成标准工具，供 Agent 在对话中按需调用。
- **怎么约束**：每个 Agent 有 **工具白名单**（见下文），防止 literature 去读本地 RAG、experiment 去瞎搜网页等越权行为。
- **怎么观察**：消息下方工作流时间线里的 tool 节点。

### 3.6 记忆分层（L1–L4）

本项目的记忆是四层，不是漏写 L2：先前 README 简表误把「会话历史」全算在 L1，把真正的 L2 挤掉了。正确划分如下：

| 层级 | 名称 | 做什么（人话） | 代码位置（大致） |
|------|------|----------------|------------------|
| **L1** | 工作记忆 | 从完整历史里**挑**给模型看的上下文：按条数截断，可选把更早内容压成摘要，避免上下文爆掉 | `memory/working.py` |
| **L2** | 会话记忆 | **完整对话的持久化存储**（SQLite 或内存）：切换会话、刷新页面后仍能拉回全部消息 | `memory/session.py`、`sqlite_store.py` |
| **L3** | 向量记忆（RAG） | 已入库文献的切块 + 向量检索，按需注入相关段落 | `memory/rag/` |
| **L4** | 结构化记忆 | 定理库：假设 / 引理 / 定理等可编辑条目，供 theory/review 等注入 | `memory/structured/` |

另外还有 **课题（Project）** 容器：把会话、文献、产出、任务等捆在同一科研主题下（不是 L1–L4 的替代，而是横向组织）。

**关系一句话**：L2 存「说过的每一句」→ L1 决定「这轮模型只看哪些」→ L3 补「论文原文片段」→ L4 补「已确认的定理条目」。

```
用户发消息
  → 写入 / 读取 L2（全量历史）
  → 经 L1 截断或摘要，得到本轮 LLM 上下文
  → 按需附加 L3（RAG）与 L4（定理库）
  → 模型生成答复 → 再写回 L2
```

---

## 4. 子 Agent 角色定位

| Agent | 一句话定位 | 典型任务 | 工具白名单（摘要） |
|-------|------------|----------|-------------------|
| **general** | 总览协调员 | 概念答疑、拆解需求、建议该切换谁 | `*`（仍遵守「不代训」边界） |
| **literature** | 外部文献员 | arXiv / 网页检索、综述、方法要点 | `arxiv__*`、`web_search__*` |
| **theory** | 理论推导主路径 | 形式化证明、读已入库 PDF、写推导迹 | `sympy__*`、`rag__*`、`web_search__*` |
| **review** | 审稿员 | 查严谨性、证明缺口、是否建议入库 L4 | **无工具** |
| **counterexample** | 反例构造员 | 最小反例、指出失效假设 | `sympy__*` |
| **experiment** | 实验顾问 | 实验计划、解读回传数据、缺数与下一步 | `filesystem__*`、`rag__*` |

**切换提示：**

- 要「搜新论文」→ literature  
- 要「读我上传的 PDF 并证明」→ theory  
- 要「挑证明毛病」→ review  
- 要「找反例推翻」→ counterexample  
- 要「实验怎么做 / 表怎么读」→ experiment  

角色提示词见 `app/server/llm/prompts.py`；白名单见 `conf/mcp_tool_whitelist.json`。

---

## 5. MCP 工具说明

配置文件：`conf/mcp_servers.json`。工具全名形如 `服务器名__工具名`。

| MCP Server | 作用（人话） | 代表工具 | 主要使用者 |
|------------|--------------|----------|------------|
| **arxiv** | 查 arXiv 论文元数据与摘要 | `search_papers`、`get_paper` | literature |
| **web_search** | 公开网页补充检索（国内建议配 Tavily） | `search` | literature、theory、general |
| **rag** | 检索本课题已入库文献片段 | `retrieve` | theory、experiment、general |
| **sympy** | 符号化简、求导、解方程、Hessian/凸性等 | `simplify_expression` 等 | theory、counterexample、general |
| **filesystem** | 在**允许目录**内列目录/读文件（辅助；非实验回传主路径） | `list_directory`、`read_file`、`write_file` | experiment、general |
| **numerical** | 轻量数值核对（梯度、谱、简单轨迹等） | `numerical_gradient` 等 | 主要 general（可选）；**不是代训** |

**实验数据入口提醒**：回传请走 Web「产出 → 回传结果」，不要把 filesystem 当成「交作业」通道。

---

## 6. 底层 LLM 与关键参数

本项目默认对接 **DeepSeek**（OpenAI 兼容接口）。密钥与参数写在 `conf/.env`（模板见 `conf/.env.example`，详表见 [`doc/ENV.md`](doc/ENV.md)）。

### 6.1 模型相关

| 配置项 | 示例 / 常见值 | 含义 |
|--------|---------------|------|
| `DEEPSEEK_API_KEY` | `sk-...` | API 密钥（必填） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 接口根地址 |
| `MODEL` | `deepseek-v4-pro` / `deepseek-v4-flash` | 模型 ID；pro 更适合长证明 |
| `MAX_TOKENS` | `384000` | 单次回复最大输出 token（含思考预算时宜大） |
| `REASONING_EFFORT` | `high` / `max` | 推理强度；`max` 时思维链通常更充分 |

前端设置抽屉还可按会话覆盖：是否开启 thinking、推理强度、历史条数、是否启用 MCP 等（部分走请求体字段，部分读服务端默认）。

### 6.2 编排与能力开关

| 配置项 | 推荐演示值 | 含义 |
|--------|------------|------|
| `ORCHESTRATION_BACKEND` | `langgraph` | 多 Agent 编排；`legacy` 为单 Agent |
| `ENABLE_MCP` | `true` | 是否加载 MCP 工具 |
| `ENABLE_RAG` | `true` | 是否启用向量检索 |
| `ROUTER_USE_LLM` | `false` | 自动路由是否用 LLM 分类（失败回退关键词） |
| `MCP_MAX_TOOL_ROUNDS` | `10` | 单轮对话最多工具循环次数 |
| `RAG_RETRIEVAL_TOP_K` | `4` | 每次检索返回的片段数 |
| `SESSION_STORE_BACKEND` | `sqlite` | 会话持久化；`memory` 重启即丢 |

### 6.3 一次请求里模型实际看到什么（概念）

1. **System Prompt**：当前 Agent 的角色说明（含工具纪律）  
2. **历史消息**：先从 **L2** 取出全量会话，再经 **L1** 截断/可选摘要后注入  
3. **可选**：**L3** RAG 命中片段、**L4** 定理摘要  
4. **用户本轮问题**  
5. 若开启工具：模型可发出 tool call → 服务端执行 MCP → 把结果再喂回模型，直至写出最终回答  

---

## 7. 前端 Web 可调用功能与执行流程

下列只覆盖 **Web 工作台实际会调用** 的能力（不罗列仅 CLI/脚本用的内部接口）。完整路径清单见 [`doc/API-ROUTES.md`](doc/API-ROUTES.md)。

### 7.1 健康检查与连接

| 功能 | 接口（示意） | 执行流程 |
|------|--------------|----------|
| 探测后端是否在线 | `GET /health` | 打开页面 / 点「重试」→ 请求健康检查 → 成功则解锁输入框并拉 MCP/历史/Token |

### 7.2 流式对话（核心）

| 功能 | 接口（示意） | 执行流程 |
|------|--------------|----------|
| 发送消息并流式接收 | `POST /v1/chat/stream` | 输入框发送 → 前端带上 `session_id` / `project_id` / Agent 与 MCP 偏好 → 服务端路由到子 Agent →（可选）多轮 MCP → DeepSeek 流式返回 → 前端渲染 reasoning/content/工具时间线/工件事件 → `done` 后刷新侧栏排序等 |
| 加载历史消息 | `GET /v1/sessions/{id}` | 切换会话 → 拉取该会话消息 → 还原工具轨迹与思维链 |
| 清空当前会话内容 | `DELETE /v1/sessions/{id}` | 顶栏「清空」→ 删服务端消息，**保留**同一 session id |
| 永久删除会话 | `DELETE /v1/sessions/{id}?purge=true` | 侧栏「×」→ 删会话记录并移出列表 |
| 列出会话 | `GET /v1/sessions` | 刷新侧栏时与本地列表合并排序 |

### 7.3 课题与会话树

| 功能 | 接口（示意） | 执行流程 |
|------|--------------|----------|
| 列出 / 创建 / 更新 / 删除课题 | `GET/POST/PATCH/DELETE /v1/projects...` | 左栏「+ 课题」或课题「属性」→ 写库 → 刷新树 |
| 关联会话到课题 | `POST /v1/projects/{pid}/sessions/{sid}` | 新建会话或移动会话时绑定课题 |
| 列出课题下会话 | `GET /v1/projects/{pid}/sessions` | 展开课题文件夹时同步归属 |
| 课题成员 / 任务看板 | `.../members`、`.../tasks` | 任务 Tab：拉列表、改状态、新建任务 |

### 7.4 文献与 RAG

| 功能 | 接口（示意） | 执行流程 |
|------|--------------|----------|
| 列出文档 | `GET /v1/documents` | 打开「文献」Tab → 展示已入库文档 |
| 上传文本 / 文件 | `POST /v1/documents`、`/upload` | 选择 PDF 等 → 切块嵌入 → 写入 Chroma |
| 从 arXiv 导入 | `POST /v1/documents/from-arxiv` | 填 arXiv ID → 拉取摘要/正文策略入库 |
| 删除文档 | `DELETE /v1/documents/{id}` | 带 `session_id` 删除单篇 |
| 查看 RAG 引用 | `GET /v1/sessions/{id}/rag-refs` | 对话后展示本轮/会话相关引用 |

### 7.5 定理库（L4）与验证

| 功能 | 接口（示意） | 执行流程 |
|------|--------------|----------|
| 定理 CRUD | `GET/POST/PATCH/DELETE /v1/memory/structured` | 「理论」Tab 新建/编辑/删除条目 |
| Markdown / PDF 导入预览 | `.../preview-markdown`、`.../import-preview` | 上传候选 → 确认后再写入 |
| 验证看板 / 记录 / 触发 | `/v1/verification/...` | 查看验证摘要；可选手动触发核对 |

### 7.6 实验产出与回传

| 功能 | 接口（示意） | 执行流程 |
|------|--------------|----------|
| 实验记录列表 / 编辑 / 删除 | `GET/PATCH/DELETE /v1/experiments/runs...` | 「产出」中管理本课题实验记录 |
| 回传文件结果 | `POST /v1/jupyter/upload-file` | 「回传结果」上传表 → 解析 → DataPacket / 记录 |
| 回传 JSON 指标 | `POST /v1/jupyter/upload-result` | 提交 summary + metrics → 同上 |
| 工件列表与维护 | `GET/POST/PATCH/DELETE /v1/artifacts...` | 推导迹、实验计划等展示与手工维护 |

### 7.7 导出、提示词优化、可观测

| 功能 | 接口（示意） | 执行流程 |
|------|--------------|----------|
| 预览 / AI 整理 / 导出 md·latex·docx·pdf | `/v1/export/...` | 「产出 → 课题笔记导出」：整理为工作笔记（非论文）→ 下载 |
| 优化用户提示词 | `POST /v1/prompt/optimize` | 输入框旁「优化提示词」→ 多风格对比 → 选用 |
| Token 统计 | `GET /v1/stats/tokens` | 顶栏显示用量 |
| MCP 状态 / 热加载 | `GET /v1/mcp/status`、`POST /v1/mcp/reload` | 设置或调试时查看工具是否连通 |
| Agent 列表 | `GET /v1/agents` | 侧栏 Agent 下拉选项 |
| 可观测摘要 | `/v1/observability/summary` 等 | 质量面板按课题汇总 |

---

## 8. 示例项目执行案例

下面用一个**虚构但完整**的小例子，说明新人如何把各模块串起来。课题主题：**「二次损失在临界点 Hessian 正定时是否为局部极小」**（示范子集）。

### 第 0 步：环境与课题

1. 配置 `conf/.env` 中的 `DEEPSEEK_API_KEY`，启动后端与前端（见第 9 节）。  
2. 左栏「+ 课题」，命名如「损失景观-局部极小」。  
3. 在该课题行点「+ 会话」，进入空白对话。

### 第 1 步：文献检索（literature）

- 侧栏选择 **literature**（或自动路由到文献）。  
- 提问：*「检索 loss landscape / local minima 相关经典论文，列 5 篇并各用三句话概括贡献。」*  
- 观察：工具时间线出现 `arxiv__search_papers`；回复含真实 arXiv 条目。  
- 记下感兴趣的 arXiv ID。

### 第 2 步：文献入库（Web「文献」）

- 上传一篇 PDF，或用 arXiv 导入。  
- 确认文档出现在列表中（RAG 已建索引）。

### 第 3 步：方法总结 + 理论证明（theory）

- 切换到 **theory**。  
- 提问：*「根据已入库文献，形式化：若 ∇L(θ\*)=0 且 Hessian 正定，则 θ\* 为局部极小。写出假设、证明步骤，并输出推导迹。」*  
- 观察：可能出现 `rag__retrieve`、可选 `sympy__*`；正文含定义/定理；右栏「理论」出现 **DerivationTrace**。  
- 将成熟结论点选写入 **定理库**。

### 第 4 步：（可选）审稿与反例

- 切 **review**：*「审阅上面证明的严谨性与假设完整性。」*  
- 若怀疑边界：切 **counterexample**：*「构造使『仅梯度为 0』不足以保证局部极小的最小反例。」*

### 第 5 步：实验计划（experiment）

- 切 **experiment**：*「针对定理库中该主张，设计一组可在本地跑的小规模数值核对计划（维度、采样点、记录字段）。」*  
- 确认「产出」中出现 **ExperimentPlan**。  
- 按计划在自己的 Python/Notebook 环境跑实验（本系统不代跑）。

### 第 6 步：回传数据并分析

- 「产出 → 回传结果」上传 CSV/Excel（含 loss、梯度范数、最小特征值等）。  
- 再问 experiment：*「根据刚回传的数据，该主张被支持还是反驳？还缺哪些字段？下一步实验怎么改？」*  
- 得到对照结论与缺数清单；必要时修订计划或回到 theory 改假设。

### 第 7 步：导出课题笔记

- 在「产出 → 课题笔记导出」生成 Markdown / Word / PDF，带走推导要点与实验对照备忘（**不是**代写论文）。

---

## 9. 快速启动与目录结构

### 环境准备

**要求**：Python 3.11+，Node.js（前端构建）

```bash
cd /path/to/agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp conf/.env.example conf/.env
# 编辑 conf/.env，填入 DEEPSEEK_API_KEY
```

密钥：[DeepSeek 开放平台](https://platform.deepseek.com/)。`conf/.env` 已 gitignore。

### 启动后端

```bash
source .venv/bin/activate
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir app
```

### 启动 Web

```bash
cd app/web && npm install && npm run dev   # 开发：http://localhost:5173
# 生产：npm run build 后由 FastAPI 托管 app/web/dist
```

### CLI（可选）

```bash
python -m client.cli --mode math --agent theory
```

### 目录布局

```
agent/
├── README.md                 # 本文件
├── app/
│   ├── server/               # FastAPI、Agent、MCP、记忆、LLM
│   ├── client/               # CLI
│   ├── shared/               # 共享 schema / 路径
│   └── web/                  # Vite + React 工作台
├── conf/                     # .env、mcp_servers.json、白名单、prompt 模板
├── doc/                      # 技术文档与愿景
├── data/                     # 运行时 DB / Chroma / 课题数据（见 doc/DATA.md）
└── docker/                   # 镜像与编排
```

> 启动 uvicorn 时必须加 `--app-dir app`（Python 包名是 `server`，代码在 `app/` 下）。

### 推荐阅读代码顺序

1. `app/shared/schemas.py` — 数据结构  
2. `app/server/config.py` — 配置项  
3. `app/server/llm/prompts.py` — 各 Agent 人设  
4. `app/server/agents/` + `graph/` — 编排与路由  
5. `app/server/api/` + `main.py` — HTTP / SSE  
6. `app/web/src/` — 工作台 UI  

---

## 10. 常见问题与扩展

| 现象 | 排查 |
|------|------|
| 启动 `ValidationError` | 检查 `conf/.env` 与 `DEEPSEEK_API_KEY` |
| Connection refused | 先启动 uvicorn |
| 重启丢会话 | `SESSION_STORE_BACKEND=sqlite` |
| 公式乱码 | `cd app/web && npm run test:math`；见 `doc/web.md` |
| literature 调 rag 失败 | 设计如此；读已上传 PDF 请切 theory |
| 实验 Agent 让你写仓库路径 | 应改用「产出→回传结果」；提示词已约束 |
| Docker / 鉴权问题 | 见 `doc/KNOWN_ISSUES.md` |

**扩展**：新 Agent → 在 `agents/config.py` 注册提示词与白名单；新 MCP → `conf/mcp_servers.json` + 白名单；架构说明见 [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md)、[`doc/mcp-config.md`](doc/mcp-config.md)。

---

## 能力边界速查

| 做 | 不做 |
|----|------|
| 文献检索与方法提炼 | 完整科研流水线自动复现 |
| PDF/DOCX/arXiv 入库 + RAG | 云端代训 / 部署推理服务 |
| 理论推导、审稿、反例思路 | 以 numerical 大规模实跑为卖点 |
| 实验计划、缺数诊断、回传数据解读 | 把「写本地 data/projects 路径」当回传 |

---

## 依赖与许可证

见 `pyproject.toml`（包版本 **2.2.0**）。MIT；请遵守 DeepSeek API 使用条款。

历史里程碑：`v0.4` 底座 · `v1.x` 产业化 · `v2.0`/`v2.1` → **`v2.2`** 言晖科研助手（理论侧多智能体）。
