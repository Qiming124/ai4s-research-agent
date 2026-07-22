# AI4S 理论侧多智能体 — 系统架构图

面向「用深度学习解决科学问题」的理论侧协作：文献方法提炼、推导、实验建议与数据解读。  
损失函数局部极小等为示范课题种子，非唯一领域。
**不**以全流程科研复现或代跑训练为核心。产品边界见 [`PRODUCT-VISION.md`](PRODUCT-VISION.md)。

本文档按**功能模块**描述系统架构，不涉及具体代码实现。  
适用于理解整体能力边界、模块职责与数据流向。

---

## 〇、产品能力（用户视角）

```mermaid
flowchart LR
  User[研究者] --> TheoryCap[理论推导]
  User --> LitCap[文献检索与方法提炼]
  User --> ExpCap[实验建议与设计]
  User --> DataCap[提交数据后解读]
  LitCap --> TheoryCap
  TheoryCap --> ExpCap
  DataCap --> ExpCap
```

| 能力 | 说明 |
|------|------|
| 理论推导 | 符号/假设工作区、分步证明、审稿清单 |
| 文献 | arXiv / 网页检索；方法提炼；RAG 入库（自动入库增强为后续） |
| 实验顾问 | 计划表、对照、成功判据；根据用户数据给下一步与缺数清单 |
| 边界 | 不代训模型、不以系统内大规模数值实跑为主路径 |

可选模块（验证账本、Torch/numerical）见架构下层「兼容能力」，非主界面叙事。Campaign S0–S8 已从代码移除。

---

## 一、系统总览（技术视角）

```mermaid
flowchart TB
  subgraph clients [接入层]
    WebUI[Web 聊天界面]
    CLI[终端 CLI]
  end

  subgraph gateway [API 网关层]
    API[HTTP / SSE 服务]
    Health[健康检查]
    Static[静态资源托管]
  end

  subgraph core [智能体核心]
    Router[意图路由 / Supervisor]
    Agents[多角色 Agent]
    CoT[思维链与推理控制]
    ToolLoop[工具调用循环]
  end

  subgraph intelligence [模型与编排]
    LLM[DeepSeek 大模型]
    LangGraph[LangGraph 编排引擎]
  end

  subgraph tools [外部能力]
    MCP[MCP 工具集群]
  end

  subgraph memory [记忆体系]
    L1[L1 工作记忆]
    L2[L2 会话记忆]
    L3[L3 RAG 知识库]
    L4[L4 结构化科研记忆]
  end

  subgraph storage [持久化存储]
    SQLite[(SQLite)]
    Chroma[(Chroma 向量库)]
    Files[(文件与理论工作区)]
  end

  WebUI --> API
  CLI --> API
  API --> Router
  Router --> Agents
  Agents --> CoT
  Agents --> ToolLoop
  Agents --> L1
  Agents --> L2
  ToolLoop --> MCP
  ToolLoop --> LangGraph
  Agents --> LLM
  LangGraph --> LLM
  Agents --> L3
  Agents --> L4
  L2 --> SQLite
  L3 --> Chroma
  L4 --> SQLite
  MCP --> Files
  API --> Static
```

---

## 二、分层架构（按职责）

```mermaid
flowchart TB
  subgraph L0 [L0 传输与呈现]
    direction LR
    T1[流式对话展示]
    T2[思考过程面板]
    T3[思维链分步卡片]
    T4[工作流时间线]
    T5[会话与设置管理]
  end

  subgraph L1_api [L1 API 服务]
    direction LR
    A1[对话接口 流式/非流式]
    A2[会话管理]
    A3[文档与 RAG 管理]
    A4[MCP 状态查询]
    A5[Token 统计]
    A6[结构化记忆 CRUD]
  end

  subgraph L2_agent [L2 Agent 编排]
    direction LR
    B1[Supervisor 路由]
    B2[General 通用助手]
    B3[Theory 理论推导]
    B4[Experiment 实验分析]
    B5[Literature 文献检索]
    B6[工具循环 ReAct]
  end

  subgraph L3_capability [L3 能力层]
    direction LR
    C1[深度思考 reasoning]
    C2[结构化 CoT 提示]
    C3[SymPy 符号验证]
    C4[RAG 检索增强]
    C5[L4 记忆注入/抽取]
  end

  subgraph L4_infra [L4 基础设施]
    direction LR
    D1[配置中心]
    D2[可观测性 日志/Token]
    D3[MCP 客户端]
    D4[数据模型校验]
  end

  L0 --> L1_api
  L1_api --> L2_agent
  L2_agent --> L3_capability
  L2_agent --> L4_infra
  L3_capability --> L4_infra
```

---

## 三、多 Agent 编排

```mermaid
flowchart LR
  User[用户消息] --> Supervisor[Supervisor 意图识别]

  Supervisor -->|通用问答| General[General Agent]
  Supervisor -->|数学/理论| Theory[Theory Agent]
  Supervisor -->|数值实验| Experiment[Experiment Agent]
  Supervisor -->|论文检索| Literature[Literature Agent]
  Supervisor -->|审稿| Review[Review Agent]
  Supervisor -->|反例| Counterexample[Counterexample Agent]
  Supervisor -->|用户指定| Explicit[显式指定 Agent]

  General --> React[ReAct 工具子图]
  Theory --> React
  Experiment --> React
  Literature --> React
  Review --> React
  Counterexample --> React

  React --> Final[最终流式回答]
  Final --> SSE[SSE 事件推送]
```

| Agent | 核心职能 |
|-------|----------|
| **Supervisor** | 分析用户意图，选择目标 Agent，发出 handoff 事件 |
| **General** | 通用科研问答、跨领域讨论 |
| **Theory** | 损失函数理论推导、CoT、SymPy/数值验证、引理持久化 |
| **Experiment** | 数值实验、谱分析、loss landscape |
| **Literature** | arXiv/网络检索、文献入库与引用 |
| **Review** | 对照审稿清单检查推导完整性 |
| **Counterexample** | 反例搜索与验证 |

---

## 四、记忆体系（L1–L4）

```mermaid
flowchart TB
  subgraph L1 [L1 工作记忆]
    W1[历史消息截断]
    W2[可选 LLM 摘要]
    W3[控制单次上下文窗口]
  end

  subgraph L2 [L2 会话记忆]
    S1[按 session_id 隔离]
    S2[消息正文]
    S3[思考过程 reasoning]
    S4[工具调用记录]
    S5[工作流时间线]
  end

  subgraph L3 [L3 RAG 向量记忆]
    R1[按会话隔离文档]
    R2[文本分块与向量化]
    R3[语义检索]
    R4[检索引用记录]
    R5[MCP 文件按需索引]
  end

  subgraph L4 [L4 结构化科研记忆]
    M1[定理 / 引理 / 假设]
    M2[实验结论 / 引用]
    M3[Theory 自动抽取持久化]
    M4[推导时注入已有知识]
  end

  Query[用户提问] --> L1
  L1 --> Agent[Agent 组装上下文]
  L2 --> L1
  L3 --> Agent
  L4 --> Agent
  Agent --> L2
  Agent --> L4
```

| 层级 | 名称 | 功能说明 |
|------|------|----------|
| **L1** | 工作记忆 | 控制单次请求带入 LLM 的历史条数，可对截断部分做摘要 |
| **L2** | 会话记忆 | 多轮对话持久化：正文、思考过程、工具调用、工作流节点 |
| **L3** | RAG 向量记忆 | 会话级文档上传与语义检索，增强回答上下文 |
| **L4** | 结构化科研记忆 | 定理/引理/假设等结构化知识，供 Theory Agent 注入与回写 |

---

## 五、MCP 工具集群

```mermaid
flowchart LR
  Agent[Agent 工具循环] --> MCPClient[MCP 客户端]

  MCPClient --> WS[网络搜索]
  MCPClient --> ARXIV[arXiv 论文]
  MCPClient --> FS[文件系统]
  MCPClient --> SYMPY[SymPy 符号计算]
  MCPClient --> RAGMCP[RAG 按需检索]
  MCPClient --> NUM[numerical 数值]

  WS -->|实时信息| Web[互联网]
  ARXIV -->|学术文献| Papers[论文库]
  FS -->|读写| DataFiles[实验/日志文件]
  SYMPY -->|梯度/Hessian| Math[符号验证]
  RAGMCP -->|会话内检索| ChromaDB[(向量库)]
  NUM -->|临界点/谱/landscape| NumPy[数值验证]
```

| 工具域 | 功能 |
|--------|------|
| **网络搜索** | 获取最新资料、术语解释、实时信息 |
| **arXiv** | 检索与整理论文元数据 |
| **文件系统** | 读取/写入允许的目录内实验日志与数据 |
| **SymPy** | 微分、Hessian、特征值等符号验证 |
| **RAG** | 从当前会话知识库检索相关片段 |
| **numerical** | 梯度、Hessian 谱、临界点分类、loss landscape、SGD 轨迹 |

---

## 六、思维链与工作流（内置 CoT）

```mermaid
sequenceDiagram
  participant U as 用户
  participant A as Agent
  participant T as 工具层
  participant M as 大模型
  participant V as 验证模块

  U->>A: 发送问题
  A->>A: 规划阶段 plan
  A->>T: 工具调用 可选
  T-->>A: 工具结果
  A->>M: 深度思考 reasoning
  M-->>A: 内部推理流
  A->>M: 生成结构化回答
  M-->>A: 问题分析 / 推理过程 / 结论
  opt Theory Agent
    A->>V: SymPy 符号验证
    V-->>A: pass / fail / skipped
  end
  A->>A: 综合阶段 synthesize
  A-->>U: SSE 工作流 + 思考 + 思维链 + 正文
```

| 能力层 | 作用 | 用户可见形式 |
|--------|------|--------------|
| **深度思考** | 模型内部推理，可开关、可调强度（high/max） | 思考过程折叠面板 |
| **结构化 CoT** | 强制分步输出（关闭 / 标准 / 严格） | 思维链分步卡片 |
| **工作流时间线** | 记录规划 → 工具 → 验证 → 综合 | 工作流节点列表 |
| **Theory 验证** | 推导后自动符号检验 | 验证状态徽章（pass/fail/skipped） |

**编排策略说明：**

- 工具调用阶段关闭 thinking，以节省 token、提升速度
- 最终回答阶段启用 thinking，流式推送 `reasoning` 事件
- Math 模式默认使用严格思维链；Theory Agent 使用专用五阶段推导，不叠加通用三节结构

---

## 七、一次完整对话的数据流

```mermaid
flowchart TD
  Start([用户输入]) --> Mode{对话模式}
  Mode -->|chat| Route[自动/手动路由]
  Mode -->|math| TheoryRoute[路由至 Theory]

  Route --> LoadHist[加载 L2 会话历史]
  TheoryRoute --> LoadHist

  LoadHist --> L1Proc[L1 截断/摘要]
  L1Proc --> RAGCheck{RAG 启用?}
  RAGCheck -->|是| RAGRetrieve[会话内 RAG 检索]
  RAGCheck -->|否| BuildPrompt[组装 System Prompt]
  RAGRetrieve --> BuildPrompt

  BuildPrompt --> CoTInject[注入思维链模式]
  CoTInject --> L4Check{Theory + L4?}
  L4Check -->|是| L4Inject[注入已证引理]
  L4Check -->|否| ToolCheck
  L4Inject --> ToolCheck{MCP 启用?}

  ToolCheck -->|是| ToolLoop[多轮工具调用]
  ToolCheck -->|否| StreamLLM[流式生成回答]
  ToolLoop --> StreamLLM

  StreamLLM --> Persist[写入 L2 会话]
  Persist --> TheoryPost{Theory 后处理?}
  TheoryPost -->|是| Verify[SymPy 验证 + L4 抽取]
  TheoryPost -->|否| SSEOut
  Verify --> SSEOut[SSE 推送到客户端]

  SSEOut --> UI[Web/CLI 分层渲染]
  UI --> End([用户看到完整回答])
```

---

## 八、Web 前端功能模块

```mermaid
flowchart TB
  subgraph layout [三栏布局]
    Left[会话列表侧栏]
    Center[主聊天区]
    Right[Agent 设置侧栏]
  end

  subgraph center_mod [主聊天区模块]
    C1[消息气泡]
    C2[工作流时间线]
    C3[思考过程面板]
    C4[思维链分步]
    C5[Markdown + KaTeX 公式]
    C6[工具调用状态]
  end

  subgraph right_mod [设置侧栏模块]
    R1[对话模式 Chat/Math]
    R2[Agent 路由选择]
    R3[推理强度与深度思考]
    R4[思维链模式]
    R5[L1 历史策略]
    R6[MCP 开关与状态]
    R7[RAG 文档管理]
    R8[RAG 引用列表]
  end

  subgraph state [状态管理]
    S1[localStorage 用户偏好]
    S2[服务端会话同步]
    S3[SSE 流式状态机]
  end

  Left --> Center
  Center --> center_mod
  Right --> right_mod
  center_mod --> S3
  right_mod --> S1
  Left --> S2
```

**消息展示顺序（助手消息）：**

1. 工作流时间线（规划 / 工具 / 验证 / 综合）
2. 思考过程面板（模型内部 reasoning）
3. 思维链分步卡片（外显结构化小节）
4. 正文（Markdown + 公式）

---

## 九、部署与运行形态

```mermaid
flowchart LR
  subgraph dev [开发环境]
    Vite[Vite 开发服务器 :5173]
    Uvicorn[FastAPI :8000]
    Vite -->|代理 API| Uvicorn
  end

  subgraph prod [生产环境]
    Docker[Docker 单镜像]
    Nginx[Nginx 可选反代]
    Docker --> Nginx
  end

  subgraph data_layer [数据目录]
    Env[环境配置]
    SessionsDB[会话数据库]
    VectorDB[向量库]
    MCPFiles[MCP 允许目录]
    TheoryWS[理论工作区]
  end

  Uvicorn --> data_layer
  Docker --> data_layer
```

| 环境 | 说明 |
|------|------|
| **开发** | 前端 Vite 热更新，API 代理至后端 8000 端口 |
| **生产** | Docker 单镜像打包前后端；可选 Nginx 反代，SSE 需关闭缓冲 |
| **数据** | 会话 SQLite、Chroma 向量库、MCP 文件目录、理论工作区均挂载于 `data/` |

---

## 十、Theory 推导闭环

```mermaid
flowchart LR
  Input[用户数学/理论问题] --> Route[路由至 Theory Agent]
  Route --> RAG[L3 RAG 注入]
  RAG --> L4[L4 引理注入]
  L4 --> CoT[五阶段分步推导]
  CoT --> Tools[SymPy / RAG MCP 工具]
  Tools --> Answer[结构化回答]
  Answer --> Verify[SymPy 自动验证]
  Verify --> Persist[引理/定理抽取至 L4]
  Persist --> SSE[verification_result + workflow_step]
```

**五阶段推导结构：**

1. 问题形式化
2. 局部分析
3. 结论（引理 / 定理 / 推论）
4. 符号验证（SymPy）
5. 边界条件与反例

---

## 十一、SSE 事件流（客户端视角）

```mermaid
flowchart LR
  Meta[meta 会话与 Agent] --> Plan[workflow_step plan]
  Plan --> Tools[tool_call_start/result/error]
  Tools --> Reason[reasoning 思考片段]
  Reason --> CoTStep[cot_step 思维链小节]
  CoTStep --> Content[content 正文片段]
  Content --> Verify[verification_result Theory]
  Verify --> Handoff[agent_handoff 可选]
  Handoff --> Done[done 结束与 Token 统计]
```

| 事件类型 | 含义 |
|----------|------|
| `meta` | 会话 ID、当前 Agent、路由原因 |
| `workflow_step` | 工作流节点（规划 / 验证 / 综合等） |
| `pipeline_stage` | 遗留兼容名（主路径用 `workflow_step`） |
| `campaign_update` | 已废弃（Campaign 移除；schema 或仍保留字面量） |
| `artifact_saved` | 产物落盘通知 |
| `tool_call_*` | MCP 工具调用开始、成功、失败 |
| `reasoning` | 模型内部思考过程片段 |
| `cot_step` | 结构化思维链小节（JSON） |
| `content` | 最终回答正文片段 |
| `verification_result` | Theory SymPy 验证结果 |
| `numerical_verification_result` | 数值验证结果 |
| `memory_warning` | L4 矛盾检测告警 |
| `agent_handoff` | 多 Agent 切换通知 |
| `done` | 流结束，含 token 用量 |

---

## 十二、模块职责速查表

| 功能域 | 核心职责 |
|--------|----------|
| **接入层** | 为用户提供对话入口（浏览器 / 终端） |
| **API 层** | 请求校验、路由分发、SSE 流式推送 |
| **Supervisor** | 意图识别与 Agent 委派 |
| **六大 Agent** | general / theory / experiment / literature / review / counterexample |
| **场景工作流 / Artifact** | lit→theory / 实验计划 / 数据→下一步；MethodCard 等工件 |
| **课题 / 验证账本** | Project 实体、任务看板、Claim 三层验证（验证非主卖点） |
| **思维链模块** | 深度思考、结构化分步、工作流可视化 |
| **工具循环** | 多轮调用 MCP，汇总结果后生成回答 |
| **LLM 层** | 对接 DeepSeek，分离 reasoning 与 content |
| **L1 工作记忆** | 控制单次请求的上下文长度 |
| **L2 会话记忆** | 多轮对话持久化与恢复 |
| **L3 RAG** | 会话级文档上传、检索、增强回答 |
| **L4 结构化记忆** | 定理/引理等科研知识的存储与复用 |
| **MCP 层** | 统一接入搜索、文献、文件、符号计算等外部能力 |
| **可观测性** | 结构化日志、Token 用量统计 |
| **配置层** | 环境变量、MCP 服务定义、工具白名单 |
| **前端** | 流式渲染、公式、设置、会话与文档管理 |

---

## 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) — 实现层架构与目录说明
- [API.md](API.md) — HTTP / SSE 接口参考
- [README.md](README.md) — 项目总览与快速开始
