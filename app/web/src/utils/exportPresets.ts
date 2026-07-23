/**
 * 导出 / 对话共用的 AI 整理提示词预设。
 * 须与后端 `server.export.ai_polish` 中 PRESET_* 保持同步。
 *
 * 产品定位：导出的是课题工作笔记（推导要点、定理清单、实验对照备忘），
 * **不是**代写可投稿论文。
 */

export const PRESET_RESEARCH_NOTES = `将草稿整理为「课题工作笔记」Markdown，供自己或协作方继续推进理论/实验。

硬性定位：本系统是言晖科研助手（理论侧顾问），**不是**写论文工具。禁止改写成可投稿论文、会议短文或 arXiv 投稿体例；不要虚构 Abstract/引言贡献列表/参考文献凑数。

固定结构（仅保留草稿里确有内容的节；空节整节省略）：
# 标题
## 课题目标与当前主张
## 关键假设与符号（简表）
## 已整理的推导要点
  - 用条目列出定义 / 引理 / 定理要点；证明保留关键步骤即可
## 开放问题与待验证项
## 实验与数据对照（仅当草稿含实验/回传数据时）
## 下一步建议

文风：清晰、可执行的工作笔记；公式 $...$ / $$...$$；禁止编造草稿没有的定理、数值、文献。`;

export const PRESET_THEOREM_CATALOG = `将草稿整理为「定理—引理汇编」Markdown（便于核对主张），**不要**写成论文。

结构：
# 标题
## 符号与假设（简表或短列表）
## 引理
对每条：### 引理 k（短名）
- **陈述**：
- **依赖假设**：
- **证明要点**（≤8 行）
- **状态**：已证 / 部分 / 待证（据草稿）
## 定理
格式同引理。
## 开放问题（若有）

禁止编造；草稿没有的字段写「未标注」。公式保留 LaTeX。`;

export const PRESET_THEORY_BRIEF = `输出「理论要点速览」工作页（便于快速对齐，非投稿摘要）：

# 标题
## 一句话主张
## 关键结论一览（表格或短列表：名称 → 一句话 → 状态）
## 关键假设（列表）
## 开放问题 / 下一步（若有，否则省略）

不要展开完整证明；不要编造草稿没有的结果；不要写成 Abstract + 贡献列表的投稿前页。`;

export const PRESET_EXPERIMENT_MEMO = `整理为「理论—实验对照备忘」（实验顾问笔记，非实验论文）：

# 标题
## 待检验的理论主张
## 已有数据摘要（数值必须来自草稿）
## 与理论对照（支持 / 反驳 / 不确定）
## 缺数清单
## 下一步实验建议

无实验内容时明确写「草稿未含实验数据」并缩短全文。禁止编造指标；不要写成可投稿实验报告体例。`;

/** @deprecated 旧名：曾用于「arXiv 论文」预设；现指向课题工作笔记 */
export const PRESET_ARXIV_THEORY = PRESET_RESEARCH_NOTES;
/** @deprecated */
export const PRESET_ABSTRACT_BRIEF = PRESET_THEORY_BRIEF;
/** @deprecated */
export const PRESET_EXPERIMENT_REPORT = PRESET_EXPERIMENT_MEMO;
/** @deprecated */
export const PAPER_FORMAT_PRESET = PRESET_RESEARCH_NOTES;

export interface PolishPreset {
  id: string;
  label: string;
  hint: string;
  text: string;
}

export const POLISH_PRESETS: PolishPreset[] = [
  {
    id: "research_notes",
    label: "课题工作笔记",
    hint: "目标 / 推导要点 / 开放问题 / 下一步（默认）",
    text: PRESET_RESEARCH_NOTES,
  },
  {
    id: "theorem_catalog",
    label: "定理汇编",
    hint: "按引理/定理清单核对，非论文",
    text: PRESET_THEOREM_CATALOG,
  },
  {
    id: "theory_brief",
    label: "理论要点速览",
    hint: "主张 + 结论一览 + 假设",
    text: PRESET_THEORY_BRIEF,
  },
  {
    id: "experiment_memo",
    label: "实验对照备忘",
    hint: "主张 × 回传数据 × 缺数与下一步",
    text: PRESET_EXPERIMENT_MEMO,
  },
];

export const EXPORT_PRESET_EVENT = "ai4s-export-preset";

export function dispatchExportPreset(presetId: string): void {
  window.dispatchEvent(
    new CustomEvent(EXPORT_PRESET_EVENT, { detail: { id: presetId } }),
  );
}
