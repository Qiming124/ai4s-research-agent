/**
 * 设置抽屉等处展示的 Agent / MCP 简要说明（与白名单产品定位对齐）。
 */

export const AGENT_LABEL_ZH: Record<string, string> = {
  auto: "智能分派",
  general: "总览协调",
  literature: "文献检索",
  theory: "理论推导",
  review: "审稿核对",
  counterexample: "反例构造",
  experiment: "实验顾问",
};

export interface AgentGuideItem {
  id: string;
  nameZh: string;
  blurb: string;
}

/** 自动路由旁可展开的子 Agent 介绍（按推荐闭环顺序） */
export const AGENT_GUIDE: AgentGuideItem[] = [
  {
    id: "general",
    nameZh: "总览协调",
    blurb: "答疑拆解、建议该切谁；可做轻量任务，专责工作请换专用角色。",
  },
  {
    id: "literature",
    nameZh: "文献检索",
    blurb: "搜 arXiv/网页、提炼方法。不能读已上传 PDF（无 RAG）。",
  },
  {
    id: "theory",
    nameZh: "理论推导",
    blurb: "形式化证明、读已入库文献、写推导迹；可用 SymPy/RAG。",
  },
  {
    id: "review",
    nameZh: "审稿核对",
    blurb: "检查严谨性与证明缺口；无工具，纯文本审查。",
  },
  {
    id: "counterexample",
    nameZh: "反例构造",
    blurb: "针对猜想构造最小反例，说明失效假设；仅 SymPy。",
  },
  {
    id: "experiment",
    nameZh: "实验顾问",
    blurb: "写实验计划、解读「产出→回传」数据与缺数；不代跑训练。",
  },
];

export function formatAgentOptionLabel(id: string, fallbackDesc?: string): string {
  const zh = AGENT_LABEL_ZH[id];
  if (id === "auto") return `自动路由 · ${zh}`;
  if (zh) return `${id} · ${zh}`;
  return fallbackDesc ? `${id} · ${fallbackDesc}` : id;
}

export interface McpGuideItem {
  id: string;
  nameZh: string;
  blurb: string;
}

export const MCP_GUIDE: McpGuideItem[] = [
  {
    id: "arxiv",
    nameZh: "arXiv",
    blurb: "按关键词或 ID 查论文元数据与摘要（文献 Agent 主用）。",
  },
  {
    id: "web_search",
    nameZh: "网页搜索",
    blurb: "公开网页补充检索；国内建议配置 Tavily。",
  },
  {
    id: "rag",
    nameZh: "课题文献检索",
    blurb: "检索本课题已上传/入库的 PDF 等片段（theory/experiment 等）。",
  },
  {
    id: "sympy",
    nameZh: "符号计算",
    blurb: "化简、求导、解方程、Hessian/凸性等轻量核对。",
  },
  {
    id: "filesystem",
    nameZh: "文件系统",
    blurb: "仅允许目录内读写辅助文件；实验回传请走「产出→回传结果」。",
  },
  {
    id: "numerical",
    nameZh: "数值辅助",
    blurb: "轻量数值核对（梯度/谱等）；不是代跑大规模训练。",
  },
];
