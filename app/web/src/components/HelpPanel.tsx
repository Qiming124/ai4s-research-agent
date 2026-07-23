import { useEffect, type MouseEvent } from "react";

interface HelpPanelProps {
  open: boolean;
  onClose: () => void;
}

/**
 * 总帮助：给科研用户的短上手指南。
 * Agent / MCP / 导出细节见设置与产出旁的「帮助」小抽屉。
 */
const SECTIONS: { title: string; steps?: string[]; items?: { name: string; desc: string }[] }[] = [
  {
    title: "这是什么",
    items: [
      {
        name: "言晖科研助手",
        desc: "协助检索文献、梳理证明、设计实验计划，并解读你上传的实验数据。不代跑大规模训练，也不代写论文。",
      },
    ],
  },
  {
    title: "五分钟上手",
    steps: [
      "左侧新建课题，再点「+ 会话」开始对话。",
      "右侧「文献」上传 PDF，或先让助手搜论文再入库。",
      "需要严格证明时，在设置里选 theory（理论推导），或开「自动路由」。",
      "实验在自己环境跑完后，到「产出 → 回传结果」上传表格或指标。",
      "想带走笔记：打开「产出 → 课题笔记导出」（详细用法点旁边「帮助」）。",
    ],
  },
  {
    title: "界面三块",
    items: [
      {
        name: "左侧",
        desc: "课题与会话。点会话只切换；和助手真正聊过后，该会话才会排到较前。",
      },
      {
        name: "中间",
        desc: "对话区。Enter 发送，Shift+Enter 换行。可点「优化提示词」把问题写清楚（不会故意换题）。",
      },
      {
        name: "右侧",
        desc: "文献 → 理论（定理库、推导迹）→ 产出（实验计划、回传、导出）。",
      },
    ],
  },
  {
    title: "想了解更多时",
    items: [
      {
        name: "子 Agent / 工具（MCP）",
        desc: "点顶栏「设置」，在「Agent 路由」或「MCP」旁点「帮助」打开小抽屉说明。",
      },
      {
        name: "导出笔记",
        desc: "右侧「产出」里「课题笔记导出」标题旁点「帮助」。",
      },
      {
        name: "公式",
        desc: "大量公式可把模式切到 Math。回答里的公式生成结束后会排版显示。",
      },
    ],
  },
  {
    title: "常见问题",
    items: [
      {
        name: "搜到了论文，但读不了我上传的 PDF？",
        desc: "搜新论文用 literature；读已入库 PDF 请切到 theory。",
      },
      {
        name: "实验数据怎么交给助手？",
        desc: "用「产出 → 回传结果」上传，不要手工拷到电脑里的项目文件夹路径。",
      },
      {
        name: "显示离线？",
        desc: "点顶栏「重试」。需本机后端服务已启动。",
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
        className="help-panel help-panel--compact"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-panel-title"
      >
        <header className="help-header">
          <div>
            <h2 id="help-panel-title">快速上手</h2>
            <p className="help-subtitle">言晖科研助手 · 看完就能开始用</p>
          </div>
          <button type="button" className="help-close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>

        <div className="help-body">
          {SECTIONS.map((section) => (
            <section key={section.title} className="help-section">
              <h3>{section.title}</h3>
              {section.steps && (
                <ol className="help-steps">
                  {section.steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              )}
              {section.items && (
                <dl className="help-dl">
                  {section.items.map((item) => (
                    <div key={item.name} className="help-item">
                      <dt>{item.name}</dt>
                      <dd>{item.desc}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>
          ))}
        </div>

        <footer className="help-footer">
          <p>按 Esc 关闭。详细角色与工具说明请到「设置 / 产出」旁的帮助抽屉查看。</p>
        </footer>
      </div>
    </div>
  );
}
