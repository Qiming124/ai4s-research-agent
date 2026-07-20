/**
 * 导出 / 对话共用的 AI 润色提示词预设。
 * 须与后端 `server.export.ai_polish` 中 PRESET_* 保持同步。
 * 版式参考 arXiv：1608.04636 / 1406.2572 / 2003.00307。
 */

export const PRESET_ARXIV_THEORY = `参照 arXiv 理论短文体例（如 Karimi et al. 1608.04636、Liu et al. 2003.00307）重写为中文 Markdown 论文。

固定结构（仅输出实际有内容的节；草稿完全缺失的节整节省略，不要写「（草稿未提供）」占位节）：
# 标题
## Abstract（或 ## 摘要）
  - 一段 180–280 字：问题、方法、主结论；勿分点。
## 1 引言
  - 动机与背景 1–2 段；贡献用编号列表 3–5 条。
## 2 问题设定与符号
  - 模型、损失、假设编号（A1…）；符号与草稿一致。
## 3 主要结果
  - 用三级标题：### 引理 k / ### 定理 k；每条含：
    - *陈述*（一两句）
    - **证明要点**（压缩草稿证明，保留关键等式）
  - 不要写成「## 定理：引理 1」这种混标题。
## 4 反例与边界（仅当草稿含反例时）
## 5 实验与数值验证（仅当草稿含实验/数值时）
## 6 结论
## 参考文献
  - 仅列草稿中出现的文献/arXiv；没有则整节省略。

文风：学术书面语、可投稿；公式 $...$ / $$...$$；禁止编造草稿没有的定理、数值、文献。`;

export const PRESET_THEOREM_CATALOG = `将草稿整理为「定理—引理汇编」Markdown（便于审稿核对），不要写成完整论文。

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

export const PRESET_ABSTRACT_BRIEF = `只输出极简投稿前页，便于快速审阅：

# 标题
## 摘要（220–320 字，一段）
## 主要贡献（3–6 条 bullet）
## 关键结论一览（表格或短列表：定理/引理名称 → 一句话结论 → 状态）
## 开放问题（若有，否则省略）

不要展开完整证明；不要编造草稿没有的结果。`;

export const PRESET_EXPERIMENT_REPORT = `整理为「理论—实验对照」技术报告（偏实验节）：

# 标题
## 摘要
## 理论预测（从草稿抽取：待验证命题 / 期望分类）
## 实验设置（网络、数据、优化器、指标；缺失则省略该小节）
## 结果与图表解读（用条目列表；数值必须来自草稿）
## 与理论对照（相符 / 部分相符 / 未覆盖）
## 局限与下一步
## 结论

无实验内容时明确写「草稿未含实验，以下仅保留理论预测」并缩短全文。禁止编造指标。`;

/** @deprecated 使用 PRESET_ARXIV_THEORY */
export const PAPER_FORMAT_PRESET = PRESET_ARXIV_THEORY;

export interface PolishPreset {
  id: string;
  label: string;
  hint: string;
  text: string;
}

export const POLISH_PRESETS: PolishPreset[] = [
  {
    id: "arxiv_theory",
    label: "arXiv 理论短文",
    hint: "摘要+编号章节+定理/引理（默认）",
    text: PRESET_ARXIV_THEORY,
  },
  {
    id: "theorem_catalog",
    label: "定理汇编",
    hint: "按引理/定理清单核对，非完整论文",
    text: PRESET_THEOREM_CATALOG,
  },
  {
    id: "abstract_brief",
    label: "摘要页",
    hint: "摘要+贡献+结论一览",
    text: PRESET_ABSTRACT_BRIEF,
  },
  {
    id: "experiment_report",
    label: "实验报告",
    hint: "理论预测与数值对照",
    text: PRESET_EXPERIMENT_REPORT,
  },
];

export const EXPORT_PRESET_EVENT = "ai4s-export-preset";

export function dispatchExportPreset(presetId: string): void {
  window.dispatchEvent(
    new CustomEvent(EXPORT_PRESET_EVENT, { detail: { id: presetId } }),
  );
}
