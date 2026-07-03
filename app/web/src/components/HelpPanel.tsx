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
        name: "定理库 (L4)",
        desc: "展示当前会话的结构化记忆（引理/定理/假设）。Theory Agent 推导后会自动抽取 ## 引理/定理 标题块并持久化。",
      },
      {
        name: "知识图谱",
        desc: "显示 L4 节点与 depends_on / cites 等依赖边。引理正文中 **依据**：引理 2 会自动建立关联。",
      },
      {
        name: "实验日志",
        desc: "列出 data/experiments/logs/ 下的实验运行记录（JSON），由 Experiment Agent 或 runner 写入。",
      },
      {
        name: "理论工作区",
        desc: "浏览 data/theory/ 种子文件：symbols.md、assumptions.md、lemmas/、counterexamples/ 等，人机共用符号基线。",
      },
      {
        name: "RAG 文档",
        desc: "上传 Markdown/文本或 PDF 到当前会话向量库；检索结果在 RAG 引用面板显示，供 theory / literature Agent 注入。",
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
    ],
  },
  {
    title: "对话与输入",
    items: [
      {
        name: "发送消息",
        desc: "底部输入框输入问题，Enter 发送，Shift+Enter 换行。多跳研究可在消息前加 /research（需 RESEARCH_PIPELINE_MODE=auto）。",
      },
      {
        name: "停止",
        desc: "生成中点击「停止」中断；已生成部分保留，未完成内容不写入历史。",
      },
      {
        name: "清空会话",
        desc: "删除当前 Session 全部历史（含服务端 SQLite），开始全新对话。生成中不可用。",
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
    title: "Agent 设置侧边栏",
    items: [
      {
        name: "打开方式",
        desc: "顶栏「设置」打开右侧栏：对话模式、Agent 路由、思考过程、历史策略、MCP、科研工作台面板。",
      },
      {
        name: "MCP 工具",
        desc: "内置 Server：web_search、arxiv、filesystem、sympy、rag、numerical。需 ENABLE_MCP=true。各 Agent 有独立工具白名单。",
      },
      {
        name: "numerical 工具",
        desc: "数值梯度、Hessian 谱、临界点分类、2D loss landscape、SGD 轨迹、随机 Hessian 采样——用于验证局部极小/鞍点直觉。",
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
        desc: "Chroma 向量库，按 session_id 隔离。支持文本上传、PDF 上传、arXiv 入库；theory/literature Agent 自动检索注入。",
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
            <p className="help-subtitle">AI4S 科研助手 v0.4 — Agent、记忆、验证与工作台</p>
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
