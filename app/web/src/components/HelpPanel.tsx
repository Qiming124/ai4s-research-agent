import { useEffect, type MouseEvent } from "react";

interface HelpPanelProps {
  open: boolean;
  onClose: () => void;
}

interface HelpSection {
  title: string;
  items: { name: string; desc: string }[];
}

const HELP_SECTIONS: HelpSection[] = [
  {
    title: "关于 Agent（v0.4）",
    items: [
      {
        name: "AI4S 科研助手",
        desc: "面向「深度学习损失函数局部极小值理论」的 AI4S 智能体：多 Agent 协作、SymPy + 数值双验证、L4 知识图谱、RAG 文献库、理论工作区与 Web 科研工作台。",
      },
      {
        name: "Session",
        desc: "每个浏览器维护会话列表（localStorage + 服务端 SQLite）。侧栏「×」会永久删除该会话；顶栏「清空会话」仅清空当前对话内容，保留 session ID。",
      },
      {
        name: "研究流水线",
        desc: "服务端设置 RESEARCH_PIPELINE_MODE=auto 时，复杂问题（或 Math 模式、/research 前缀）会依次经过：文献检索 → 理论推导 → 数值实验（按需）→ 审稿。流式中会出现 pipeline_stage 事件。",
      },
    ],
  },
  {
    title: "多 Agent 协作",
    items: [
      {
        name: "启用方式",
        desc: "conf/.env 设置 ORCHESTRATION_BACKEND=langgraph（或 multi）、ENABLE_MCP=true。侧栏可选手动指定 Agent 或「自动路由」。",
      },
      {
        name: "general",
        desc: "通用科研问答与总结，可使用全部 MCP 工具。",
      },
      {
        name: "theory",
        desc: "数学推导专用：注入理论工作区符号/假设、L4 引理记忆；调用 SymPy 与 numerical MCP；推导后自动 SymPy → 数值验证，并抽取引理写入 L4。",
      },
      {
        name: "experiment",
        desc: "数值验证与实验日志：读取 data/experiments/，调用 numerical MCP（Hessian 谱、loss landscape、SGD 轨迹等），输出结构化实验结论。",
      },
      {
        name: "literature",
        desc: "arXiv / 网络检索与文献综述；可将论文通过 API 或 from-arxiv 入库到 RAG。",
      },
      {
        name: "review",
        desc: "对照 review-checklist.md 审稿：检查符号一致性、假设完整性、证明缺口，输出是否建议写入 L4。",
      },
      {
        name: "Agent 切换指示",
        desc: "流式过程中顶栏显示当前 Agent；agent_handoff 事件表示 Supervisor 委派；Math 模式优先路由 theory。",
      },
    ],
  },
  {
    title: "科研工作台（右侧栏）",
    items: [
      {
        name: "四个阶段 Tab",
        desc: "文献（上传/RAG 引用）→ 理论（定理库、资产、假设图、关系图谱、工作区）→ 验证（验证看板、可观测性）→ 产出（实验、Jupyter、论文导出）。各分区可折叠展开。",
      },
      {
        name: "定理库 (L4)",
        desc: "「理论」Tab 内展示当前会话的结构化记忆（引理/定理/假设）。Theory Agent 推导后会自动抽取 ## 引理/定理 标题块并持久化。",
      },
      {
        name: "关系图谱",
        desc: "「理论」Tab 内显示 L4 节点与 depends_on / cites 等依赖边。引理正文中 **依据**：引理 2 会自动建立关联。",
      },
      {
        name: "实验与导出",
        desc: "「产出」Tab：实验日志、Jupyter；论文导出默认勾选 AI「论文格式」预设（摘要→引言→定理→实验→结论），可预览后导出 MD/Word/PDF。",
      },
      {
        name: "理论工作区",
        desc: "「理论」Tab 内浏览 data/theory/ 种子文件：symbols.md、assumptions.md 等，人机共用符号基线。",
      },
      {
        name: "RAG 文档",
        desc: "「文献」Tab：支持 PDF/DOCX/Markdown 上传、arXiv 一键导入与 RAG 引用列表。",
      },
    ],
  },
  {
    title: "验证与工作流",
    items: [
      {
        name: "工作流时间线",
        desc: "每条回答下方展示：规划 → 工具调用 → SymPy 验证 → 数值验证 → 综合回答。verify 节点显示 pass/fail/skipped。",
      },
      {
        name: "SymPy 符号验证",
        desc: "Theory 推导结束后自动求梯度与 Hessian 特征值；verification_result SSE 含 JSON 详情。",
      },
      {
        name: "数值验证 fallback",
        desc: "SymPy 跳过或失败时，自动调用 numerical__critical_point_classify；numerical_verification_result SSE 报告临界点分类。",
      },
      {
        name: "Loss Landscape 可视化",
        desc: "当 numerical__loss_landscape_2d 或 sgd_trajectory 工具返回 viz_type 数据时，消息内会嵌入简易 2D 等高线或轨迹摘要。",
      },
      {
        name: "记忆矛盾告警",
        desc: "新定理与已有假设冲突时，memory_warning SSE 会在消息中显示琥珀色提示。",
      },
      {
        name: "流水线阶段条",
        desc: "多跳研究时，消息顶部显示「流水线: literature → theory → …」阶段路径（来自 pipeline_stage 事件）。",
      },
      {
        name: "工具调用轨迹",
        desc: "工作流时间线中 tool 节点展示 MCP 工具名与执行状态；顶栏同步显示当前 running 工具。",
      },
    ],
  },
  {
    title: "顶栏与连接状态",
    items: [
      {
        name: "连接状态",
        desc: "显示「已连接」或「离线」。后端未启动时输入框禁用，可点「重试」重新检测并刷新 MCP、历史与 Token 统计。",
      },
      {
        name: "会话 ID",
        desc: "当前会话短 ID，便于对照 API 调试（完整 ID 存于 localStorage 与服务端 SQLite）。",
      },
      {
        name: "当前 Agent / 工具",
        desc: "流式生成时显示正在处理的 Agent；调用 MCP 时额外显示工具名（如 sympy__differentiate）。",
      },
      {
        name: "Token 统计",
        desc: "本会话累计 token 用量（需服务端 ENABLE_TOKEN_STATS=true）。每条回答底部也会显示当轮 usage。",
      },
      {
        name: "停止生成",
        desc: "生成中顶栏出现「停止」按钮，与流式中断逻辑相同：保留已输出内容。",
      },
      {
        name: "清空会话",
        desc: "顶栏按钮：清空当前会话全部消息（DELETE /v1/sessions/{id}），保留 session ID，与左侧「×」删除会话不同。",
      },
    ],
  },
  {
    title: "会话管理（左侧栏）",
    items: [
      {
        name: "三个 Tab",
        desc: "左栏分为「会话」「课题」「任务」三个 Tab，避免一屏堆叠过多面板。默认打开会话列表。",
      },
      {
        name: "新建会话",
        desc: "「会话」Tab 中点击「+ 新建」创建新 session_id，自动切换并开始空白对话。",
      },
      {
        name: "切换会话",
        desc: "点击列表项切换；切换后从服务端加载历史（需 SESSION_STORE_BACKEND=sqlite）。",
      },
      {
        name: "删除会话",
        desc: "点击会话右侧「×」永久删除（purge=true），含服务端数据与列表项；若删的是当前会话则自动切到下一个或新建。",
      },
      {
        name: "删除课题",
        desc: "课题「属性」中「删除课题」：整包删除会话、Campaign 与工作区文件（需确认）。默认课题不可删。",
      },
      {
        name: "历史恢复",
        desc: "刷新页面后自动恢复上次会话列表与消息。加载失败时顶栏下方显示琥珀色提示，可点重试或检查后端。",
      },
    ],
  },
  {
    title: "对话与输入",
    items: [
      {
        name: "发送消息",
        desc: "底部多行输入框，Enter 发送，Shift+Enter 换行。后端离线或生成中时输入禁用。科研版可在输入区选「AI润色提示词」填入导出同款体例；多跳研究仍可在消息前加 /research（需 RESEARCH_PIPELINE_MODE=auto）。",
      },
      {
        name: "流式占位提示",
        desc: "生成中若尚无正文，会显示「正在思考…」「正在调用工具：xxx…」或工作流节点标题，便于判断当前进度。",
      },
    ],
  },
  {
    title: "显示与推理设置",
    items: [
      {
        name: "显示思考过程",
        desc: "勾选后在每条回答中展开「思考过程」面板（DeepSeek reasoning 纯文本，流式时自动展开）。关闭后仅显示最终回答。",
      },
      {
        name: "推理策略：服务端默认",
        desc: "勾选时不向 API 发送 enable_thinking / reasoning_effort，由 .env 的 REASONING_EFFORT 决定；取消后可本地覆盖。",
      },
      {
        name: "深度思考与推理强度",
        desc: "enable_thinking 开启 DeepSeek thinking 通道；推理强度 high（较快）或 max（更深、耗 token 更多）。",
      },
      {
        name: "思维链模式",
        desc: "控制回答结构：关闭 / 标准（问题分析→推理→结论）/ 严格（强制 Markdown 三节）。Math 模式自动升为 strict；解析后显示「思维链」分步面板。",
      },
      {
        name: "Theory 五阶段推导",
        desc: "路由到 theory Agent 时，服务端使用专用推导 prompt，与工作流时间线的 plan/verify 节点配合，不限于侧栏 cot_mode。",
      },
    ],
  },
  {
    title: "公式显示",
    items: [
      {
        name: "LaTeX 渲染",
        desc: "回答中的 $...$（行内）与 $$...$$（独立成行）在生成完成后自动渲染。分段函数、矩阵、多行推导必须用 $$...$$。",
      },
      {
        name: "Math 模式",
        desc: "含大量公式的问题请切换到 Math 模式。模型使用更严格 LaTeX 规范，并路由到 theory Agent。",
      },
      {
        name: "生成过程中",
        desc: "流式输出时公式以原文显示，避免未闭合 LaTeX 报错；生成结束后切换为排版公式。",
      },
      {
        name: "自动修复与局限",
        desc: "系统会尝试补全未闭合的 $、裸 \\begin{cases} 等。公式被截断或 $...$ 被换行拆开时可能显示琥珀色原文——可请模型「用完整 $$...$$ 重写」。",
      },
    ],
  },
  {
    title: "科研工作台（右栏）",
    items: [
      {
        name: "打开方式",
        desc: "顶栏「设置」按钮打开右侧浮层抽屉（非内嵌面板）：对话模式、Agent 路由、显示与思维链、L1 上下文、MCP。生成中部分控件禁用。",
      },
      {
        name: "Chat / Math 模式",
        desc: "Chat 为通用对话；Math 使用数学推导 prompt、优先 theory 路由，并默认严格思维链。",
      },
      {
        name: "Agent 路由",
        desc: "可选自动路由（Supervisor）或手动指定 general/theory/experiment/literature/review；偏好存 localStorage。",
      },
      {
        name: "MCP 工具",
        desc: "「MCP：服务端默认」勾选时跟随 .env 的 ENABLE_MCP；取消后可本地开关「启用 MCP 工具」。侧栏列出各 Server 连接状态与工具 schema，可点「刷新」。",
      },
      {
        name: "内置 Server",
        desc: "web_search、arxiv、filesystem、sympy、rag、numerical。各 Agent 有独立白名单（conf/mcp_tool_whitelist.json）。",
      },
      {
        name: "numerical 工具",
        desc: "数值梯度、Hessian 谱、临界点分类、2D loss landscape、SGD 轨迹、随机 Hessian 采样——用于验证局部极小/鞍点直觉。",
      },
      {
        name: "面板刷新",
        desc: "定理库、知识图谱、实验日志、工作区、RAG 文档/引用、MCP 状态均支持手动「刷新」拉取最新数据。",
      },
    ],
  },
  {
    title: "记忆层级",
    items: [
      {
        name: "L1 工作记忆",
        desc: "每次请求前从 L2 读取历史，按保留条数/摘要策略裁剪后送给 LLM；不修改数据库。",
      },
      {
        name: "L2 会话存储",
        desc: "SQLite 持久化全部消息（含 reasoning、tool_calls、workflow_steps）。刷新页面可恢复。",
      },
      {
        name: "L3 RAG",
        desc: "Chroma 向量库，按 session_id 隔离。Web 可上传文本/Markdown；PDF 与 arXiv 通过 API 入库。theory/literature Agent 自动检索注入，引用见「RAG 引用」面板。",
      },
      {
        name: "L4 结构化记忆",
        desc: "定理/引理/假设/实验结论 SQLite 存储 + 知识图谱边。theory/review Agent 自动注入；全局引理来自 data/theory/lemmas/ 同步。",
      },
      {
        name: "理论工作区文件",
        desc: "data/theory/symbols.md 与 assumptions.md 在 theory/review 推导前注入 system prompt，保证符号与假设一致。",
      },
    ],
  },
  {
    title: "历史策略（L1）",
    items: [
      {
        name: "概述",
        desc: "只影响发给 LLM 的上下文长度，不删除数据库完整历史。长对话可减少 token 消耗。",
      },
      {
        name: "服务端默认",
        desc: "勾选时使用 .env 的 MAX_HISTORY_MESSAGES 与 ENABLE_HISTORY_SUMMARY；取消后可在侧栏单独设置。",
      },
      {
        name: "保留条数",
        desc: "0 = 不截断；N>0 时只发送最近 N 条消息给模型。",
      },
      {
        name: "LLM 摘要旧消息",
        desc: "截断启用时，对被截掉的旧消息生成摘要注入 system；额外消耗 token，默认关闭。",
      },
    ],
  },
  {
    title: "CLI 与 API",
    items: [
      {
        name: "CLI",
        desc: "python -m client.cli --mode math --agent theory；支持 --agent review / experiment / literature。",
      },
      {
        name: "主要 API",
        desc: "POST /v1/chat/stream（SSE）、GET /v1/memory/structured/graph、GET /v1/theory/workspace、POST /v1/documents/upload、POST /v1/export/latex。详见 doc/API.md。",
      },
      {
        name: "Docker",
        desc: "docker compose -f docker/docker-compose.yml up -d --build；访问 http://localhost:8000。data/ 卷持久化会话与 Chroma。",
      },
    ],
  },
];

export function HelpPanel({ open, onClose }: HelpPanelProps) {
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const handleBackdropClick = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="help-overlay" onClick={handleBackdropClick} role="presentation">
      <div
        className="help-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-panel-title"
      >
        <header className="help-header">
          <div>
            <h2 id="help-panel-title">使用帮助</h2>
            <p className="help-subtitle">AI4S 科研助手 v0.4 — 界面、Agent、记忆与验证</p>
          </div>
          <button type="button" className="help-close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>

        <div className="help-body">
          {HELP_SECTIONS.map((section) => (
            <section key={section.title} className="help-section">
              <h3>{section.title}</h3>
              <dl className="help-dl">
                {section.items.map((item) => (
                  <div key={item.name} className="help-item">
                    <dt>{item.name}</dt>
                    <dd>{item.desc}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>

        <footer className="help-footer">
          <p>
            偏好设置保存在浏览器 localStorage。完整文档见仓库 doc/README.md；按 Esc 关闭本面板。
          </p>
        </footer>
      </div>
    </div>
  );
}
