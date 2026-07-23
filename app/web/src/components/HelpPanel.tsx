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
    title: "关于助手（v2.2）",
    items: [
      {
        name: "AI4S 理论侧多智能体",
        desc: "面向「用深度学习解决科学问题」的理论侧协作：检索并阅读文献、理论推导、实验建议与下一步方向、解读用户提交的数据。损失函数局部极小等为示范子集。不代跑大规模训练、不部署模型、不以全流程科研复现为核心。",
      },
      {
        name: "Session",
        desc: "每个浏览器维护会话列表（localStorage + 服务端 SQLite）。侧栏「×」会永久删除该会话；顶栏「清空会话」仅清空当前对话内容，保留 session ID。",
      },
      {
        name: "能力闭环",
        desc: "literature → theory →（可选 review/counterexample）→ experiment（计划/读数/下一步）。详见 doc/PRODUCT-VISION.md。",
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
        desc: "理论侧总览问答；可建议实验但不代跑训练；复杂任务请切换专用 Agent。",
      },
      {
        name: "theory",
        desc: "数学推导主路径：注入符号/假设与 L4；可读文献方法并形式化；SymPy 作可选符号辅助。",
      },
      {
        name: "experiment",
        desc: "实验顾问：实验目标与计划表、对照与记录字段；读取用户提交日志/结果并给出下一步与缺数清单。不以 numerical 实跑为核心。",
      },
      {
        name: "literature",
        desc: "arXiv / 网络检索；方法提炼（假设、损失、公式骨架）；可建议将论文入库 RAG。",
      },
      {
        name: "review",
        desc: "对照 review-checklist.md 审稿：符号一致性、假设完整性、证明缺口；可建议补文献或补实验。",
      },
      {
        name: "Agent 切换指示",
        desc: "流式过程中顶栏显示当前 Agent；agent_handoff 表示路由委派；Math 模式优先 theory。",
      },
    ],
  },
  {
    title: "工作台（右侧栏）",
    items: [
      {
        name: "三个 Tab",
        desc: "文献（上传/RAG）→ 理论（定理库、推导迹）→ 产出（实验计划/记录与导出）。侧重读文献、推导与数据解读，非代跑实验。",
      },
      {
        name: "定理库 (L4)",
        desc: "「理论」Tab：可新建/编辑/删除条目，支持 Markdown 与 PDF 一键导入（候选确认后入库）。Theory 推导仍可自动抽取。",
      },
      {
        name: "推导迹",
        desc: "「理论」Tab：Theory Agent 输出的分步推导工件（DerivationTrace）。",
      },
      {
        name: "实验记录与导出",
        desc: "「产出」Tab：实验计划与读数建议（可手工新建/编辑/删除）、本课题实验记录 CRUD（与其他课题隔离），以及论文导出。",
      },
      {
        name: "RAG 文档",
        desc: "「文献」Tab：支持 PDF/DOCX/Markdown 上传、arXiv 导入与 RAG 引用列表。",
      },
    ],
  },
  {
    title: "工作流与工具",
    items: [
      {
        name: "工作流时间线",
        desc: "每条回答下方可展示：规划 → 工具调用 → 综合回答。遗留的 SymPy/数值验证节点若出现，视为可选核对。",
      },
      {
        name: "SymPy 符号辅助",
        desc: "Theory 可对简单可符号化损失调用 SymPy；非必经大规模数值验证。",
      },
      {
        name: "记忆矛盾告警",
        desc: "新定理与已有假设冲突时，memory_warning 会在消息中显示提示。",
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
        name: "课题会话树",
        desc: "左栏为课题文件夹树（含会话）。可在文件夹内新建会话；课题属性可编辑。",
      },
      {
        name: "新建会话",
        desc: "点击「+ 新建」创建新 session_id，自动切换并开始空白对话。",
      },
      {
        name: "切换会话",
        desc: "点击列表项切换；切换后从服务端加载历史（需 SESSION_STORE_BACKEND=sqlite）。",
      },
      {
        name: "删除会话",
        desc: "点击会话右侧「×」永久删除（purge=true）；若删的是当前会话则自动切到下一个或新建。",
      },
      {
        name: "删除课题",
        desc: "课题「属性」中「删除课题」：整包删除会话与工作区文件（需确认）。默认课题不可删。",
      },
      {
        name: "历史恢复",
        desc: "刷新页面后自动恢复上次会话列表与消息。加载失败时顶栏下方显示提示，可点重试或检查后端。",
      },
    ],
  },
  {
    title: "对话与输入",
    items: [
      {
        name: "发送消息",
        desc: "底部多行输入框，Enter 发送，Shift+Enter 换行。点「优化提示词」可做 AI 多风格对比，或选用内置导出润色体例。顶栏 Token 右侧可切换 Chat / Math。推荐手动选择 theory / literature / experiment。",
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
        desc: "控制回答结构：关闭 / 标准（问题分析→推理→结论）/ 严格（强制 Markdown 三节）。Math 模式自动升为 strict。",
      },
      {
        name: "Theory 分阶段推导",
        desc: "路由到 theory Agent 时使用专用推导 prompt（形式化→局部分析→结论→可选符号辅助）。",
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
    title: "设置与 MCP",
    items: [
      {
        name: "打开方式",
        desc: "顶栏「设置」按钮打开右侧浮层抽屉：对话模式、Agent 路由、显示与思维链、L1 上下文、MCP。生成中部分控件禁用。",
      },
      {
        name: "Chat / Math 模式",
        desc: "Chat 为通用对话；Math 使用数学推导 prompt、优先 theory 路由，并默认严格思维链。",
      },
      {
        name: "Agent 路由",
        desc: "可选自动路由或手动指定 general/theory/experiment/literature/review；偏好存 localStorage。",
      },
      {
        name: "MCP 工具",
        desc: "「MCP：服务端默认」勾选时跟随 .env 的 ENABLE_MCP；取消后可本地开关「启用 MCP 工具」。侧栏列出各 Server 连接状态。",
      },
      {
        name: "内置 Server",
        desc: "web_search、arxiv、filesystem、sympy、rag、numerical。各 Agent 有独立白名单。numerical 为可选核对，非代跑实验主路径。",
      },
      {
        name: "面板刷新",
        desc: "定理库、实验日志、RAG 文档/引用、MCP 状态均支持手动「刷新」。",
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
        desc: "Chroma 向量库，按 session_id 隔离。Web 可上传文本/Markdown；PDF 与 arXiv 通过 API 入库。theory/literature 可检索注入。",
      },
      {
        name: "L4 结构化记忆",
        desc: "定理/引理等 SQLite 卡片库。支持手工 CRUD 与 PDF/Markdown 导入；theory/review 可注入。",
      },
      {
        name: "理论符号/假设注入",
        desc: "假设与符号以对话及 L4 定理库为准；已下线的 symbols/assumptions 种子文件不再注入 prompt。",
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
        desc: "POST /v1/chat/stream（SSE）、GET/POST /v1/memory/structured、POST /v1/documents/upload、POST /v1/export/latex。详见 doc/API.md。",
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
            <p className="help-subtitle">AI4S 理论侧多智能体 v2.2 — 文献、推导、实验建议</p>
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
            偏好设置保存在浏览器 localStorage。完整文档见仓库 doc/README.md 与 doc/PRODUCT-VISION.md；按 Esc 关闭本面板。
          </p>
        </footer>
      </div>
    </div>
  );
}
