/**
 * 情境帮助文案：给科研用户看的短说明（非开发文档）。
 * 详细说明放在设置 / 导出旁的小抽屉，总帮助只保留上手路径。
 */

export interface HelpBlock {
  title: string;
  body: string;
}

export const AGENT_HELP_TITLE = "子 Agent 怎么用";

export const AGENT_HELP_BLOCKS: HelpBlock[] = [
  {
    title: "一句话",
    body: "不同问题交给不同「助手角色」。可选自动分派，或自己指定。专责任务用专用角色效果更好。",
  },
  {
    title: "推荐怎么走",
    body: "先 literature 找论文 → 在「文献」上传入库 → theory 读库内文献并推导 → 需要时用 review 审严谨性或 counterexample 找反例 → experiment 写计划、解读你回传的数据。",
  },
  {
    title: "general · 总览协调",
    body: "问概念、拆任务、不知道找谁时用它。复杂专责工作请再切到下面角色。",
  },
  {
    title: "literature · 文献检索",
    body: "搜 arXiv / 网页、整理列表与方法要点。注意：它读不了你已上传的 PDF；读本地入库文献请用 theory。",
  },
  {
    title: "theory · 理论推导",
    body: "写证明、形式化、读已入库 PDF、生成推导迹。数学推导的主路径。",
  },
  {
    title: "review · 审稿核对",
    body: "检查推导是否严谨、假设是否齐全、有无证明缺口。不调用外部工具。",
  },
  {
    title: "counterexample · 反例构造",
    body: "针对某个猜想构造尽量简单的反例，说明哪条假设失效。",
  },
  {
    title: "experiment · 实验顾问",
    body: "设计实验计划、解读「产出 → 回传结果」里的表/指标、列出缺数与下一步。系统不代跑大规模训练。",
  },
];

export const MCP_HELP_TITLE = "工具（MCP）说明";

export const MCP_HELP_BLOCKS: HelpBlock[] = [
  {
    title: "是什么",
    body: "开启后，助手可以调用外部工具（搜论文、符号计算、读已入库文献等）。对话下方时间线会显示正在调用的工具。",
  },
  {
    title: "怎么开",
    body: "默认跟随服务端配置。若取消「服务端默认」，可手动开关「启用 MCP」。上方列表显示各工具服务是否已连接。",
  },
  {
    title: "arxiv · 论文库",
    body: "按关键词或编号查 arXiv 论文摘要，适合 literature。",
  },
  {
    title: "web_search · 网页搜索",
    body: "补充公开网页资料。国内网络建议管理员配置 Tavily 密钥。",
  },
  {
    title: "rag · 课题文献",
    body: "在你已上传到本课题的 PDF/文档里检索相关段落。读已入库材料请用 theory 等有权限的角色。",
  },
  {
    title: "sympy · 符号计算",
    body: "化简、求导、解方程等，辅助核对公式，不能代替完整证明叙述。",
  },
  {
    title: "filesystem · 文件（受限）",
    body: "只在允许目录内辅助读写。实验结果请用「产出 → 回传结果」上传，不要手工拷到仓库路径。",
  },
  {
    title: "numerical · 数值辅助",
    body: "可选的轻量数值核对。不是代你训练模型或跑大规模实验。",
  },
];

export const EXPORT_HELP_TITLE = "课题笔记导出";

export const EXPORT_HELP_BLOCKS: HelpBlock[] = [
  {
    title: "用途",
    body: "把本会话里的推导要点、定理清单、实验对照整理成 Markdown / Word / PDF 带走。这是工作笔记，不是代写可投稿论文。",
  },
  {
    title: "建议步骤",
    body: "1）填笔记标题；2）选用一种整理体例（或关掉 AI 整理直接导出原稿）；3）可先「预览 AI 整理」；4）再导出 MD / Word / PDF（LaTeX 暂不走 AI 整理）。",
  },
  {
    title: "整理体例",
    body: "课题工作笔记（默认）、定理汇编、理论要点速览、实验对照备忘。都会要求忠实你已有内容，不编造结果。",
  },
  {
    title: "内容从哪来",
    body: "优先用定理库与会话中的推导/计划；若还没有，会回退用本会话的助手回答。没有实质内容时无法导出。",
  },
];
