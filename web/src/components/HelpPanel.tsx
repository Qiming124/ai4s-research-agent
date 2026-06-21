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
    title: "关于 Agent",
    items: [
      {
        name: "AI4S 科研助手",
        desc: "基于 DeepSeek 的多轮对话 Agent，面向深度学习与损失函数极小值等科研问题。当前为 Phase 2A：支持会话持久化、流式输出与可配置的工作记忆策略。",
      },
      {
        name: "Session",
        desc: "每个浏览器会绑定一个会话 ID。刷新页面后会自动从服务端恢复完整对话历史（含思考过程）。顶栏显示的 Session 为当前会话的短 ID。",
      },
      {
        name: "Agent 指示",
        desc: "生成回答时顶栏会显示当前处理的 Agent 名称（如 general）。后续版本将扩展为多 Agent 协作。",
      },
    ],
  },
  {
    title: "对话与输入",
    items: [
      {
        name: "发送消息",
        desc: "在底部输入框输入问题，点击「发送」或按 Enter 发送；Shift + Enter 换行。",
      },
      {
        name: "停止",
        desc: "生成过程中可点击「停止」中断当前回复。已生成的部分内容会保留，未完成的部分不会写入历史。",
      },
      {
        name: "清空会话",
        desc: "删除当前 Session 的全部历史消息（服务端存储一并清除），开始全新对话。生成中不可用。",
      },
    ],
  },
  {
    title: "公式显示",
    items: [
      {
        name: "LaTeX 渲染",
        desc: "回答中的 $...$（行内）与 $$...$$（独立成行）公式会在生成完成后自动渲染。分段函数、矩阵等复杂公式建议使用 $$...$$。",
      },
      {
        name: "生成过程中",
        desc: "流式输出时公式以原文显示，避免未闭合的 LaTeX 导致渲染错误；生成结束后会自动切换为排版后的公式。",
      },
      {
        name: "渲染失败",
        desc: "若 LaTeX 语法不完整或不被支持，完成后会保留原文并以琥珀色提示标出。系统会尝试自动补全未闭合的 $ 定界符和 \\begin{cases} 等环境。",
      },
    ],
  },
  {
    title: "Agent 设置侧边栏",
    items: [
      {
        name: "打开方式",
        desc: "点击顶栏「设置」打开右侧侧边栏，集中配置对话模式、思考过程显示、上下文策略与 MCP 工具。",
      },
      {
        name: "MCP 工具",
        desc: "侧边栏可查看已配置的 MCP Server 与工具列表，并选择是否启用工具调用。需在服务端 .env 设置 ENABLE_MCP=true 后工具才会真正可用。",
      },
    ],
  },
  {
    title: "顶栏选项",
    items: [
      {
        name: "设置",
        desc: "打开 Agent 设置侧边栏：Chat/Math 模式、思考过程、历史截断与 MCP 开关。",
      },
      {
        name: "停止 / 清空 / 帮助",
        desc: "生成中可停止；清空会删除当前 Session 全部历史；帮助面板提供详细说明。",
      },
    ],
  },
  {
    title: "历史策略（L1 工作记忆）",
    items: [
      {
        name: "概述",
        desc: "L1 只影响发给 LLM 的上下文长度，不会删除数据库中的完整历史。长对话时可减少 token 消耗、避免超出上下文窗口。",
      },
      {
        name: "服务端默认",
        desc: "勾选时使用服务端 .env 中的 MAX_HISTORY_MESSAGES 与 ENABLE_HISTORY_SUMMARY 配置；取消勾选后可在设置侧边栏单独设置。",
      },
      {
        name: "保留条数",
        desc: "设为 0 表示不截断，将全部历史发送给模型。设为 N（N>0）时只向 LLM 发送最近 N 条消息，更早的消息不参与本轮推理。",
      },
      {
        name: "LLM 摘要旧消息",
        desc: "在截断启用（保留条数 > 0）时，对被截掉的旧消息调用 LLM 生成摘要，作为 system 上下文补充。会额外消耗 API 调用与 token，默认关闭。",
      },
    ],
  },
  {
    title: "记忆层级",
    items: [
      {
        name: "L2 会话存储",
        desc: "SQLite 持久化全部消息（含 reasoning）。服务重启、页面刷新后历史不丢失。",
      },
      {
        name: "L1 工作记忆",
        desc: "每次请求前，从 L2 读取完整历史，再按上述策略裁剪后送给 LLM。裁剪结果不写入数据库。",
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
            <p className="help-subtitle">Agent 功能与各选项说明</p>
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
          <p>偏好设置（模式、思考过程、历史策略）保存在浏览器 localStorage 中。</p>
        </footer>
      </div>
    </div>
  );
}
