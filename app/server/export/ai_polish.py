# 导出前 AI 润色：按 arXiv / 会议论文体例改写会话草稿。

from __future__ import annotations

import logging
import re

from server.llm.client import get_deepseek_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 版式参考（抽样 arXiv：1608.04636 Karimi PL、1406.2572 Dauphin 鞍点、
# 2003.00307 Liu PL*）：标题居中约 14–17pt；摘要略小于正文；正文约 10–11pt；
# 一级节名加粗；定理用 “Theorem k.” + 斜体陈述。前端预设与下列常量同步。
# ---------------------------------------------------------------------------

PRESET_ARXIV_THEORY = """参照 arXiv 理论短文体例（如 Karimi et al. 1608.04636、Liu et al. 2003.00307）重写为中文 Markdown 论文。

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

文风：学术书面语、可投稿；公式 $...$ / $$...$$；禁止编造草稿没有的定理、数值、文献。"""

PRESET_THEOREM_CATALOG = """将草稿整理为「定理—引理汇编」Markdown（便于审稿核对），不要写成完整论文。

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

禁止编造；草稿没有的字段写「未标注」。公式保留 LaTeX。"""

PRESET_ABSTRACT_BRIEF = """只输出极简投稿前页，便于快速审阅：

# 标题
## 摘要（220–320 字，一段）
## 主要贡献（3–6 条 bullet）
## 关键结论一览（表格或短列表：定理/引理名称 → 一句话结论 → 状态）
## 开放问题（若有，否则省略）

不要展开完整证明；不要编造草稿没有的结果。"""

PRESET_EXPERIMENT_REPORT = """整理为「理论—实验对照」技术报告（偏实验节）：

# 标题
## 摘要
## 理论预测（从草稿抽取：待验证命题 / 期望分类）
## 实验设置（网络、数据、优化器、指标；缺失则省略该小节）
## 结果与图表解读（用小节列表；数值必须来自草稿）
## 与理论对照（相符 / 部分相符 / 未覆盖）
## 局限与下一步
## 结论

无实验内容时明确写「草稿未含实验，以下仅保留理论预测」并缩短全文。禁止编造指标。"""

# 默认 = arXiv 理论短文
PAPER_FORMAT_INSTRUCTIONS = PRESET_ARXIV_THEORY

EXPORT_PRESETS: dict[str, str] = {
    "arxiv_theory": PRESET_ARXIV_THEORY,
    "theorem_catalog": PRESET_THEOREM_CATALOG,
    "abstract_brief": PRESET_ABSTRACT_BRIEF,
    "experiment_report": PRESET_EXPERIMENT_REPORT,
}

_SYSTEM_PROMPT = """你是机器学习优化 / 深度学习理论方向的学术编辑。参考 arXiv 会议论文常见体例（标题居中、摘要独立成段、正文分节编号、定理陈述简洁、证明可压缩为要点），把用户草稿改写成**可直接导出 Word/PDF 的 Markdown**。

硬性规则：
1. 只输出 Markdown 正文（以 `#` 标题开头）；不要用 ``` 围栏包全文；不要附「改动说明」。
2. 严格按用户「润色要求」的结构输出；**无内容的节整节删除**，不要保留空壳标题。
3. 忠实草稿：不捏造定理、证明步骤、实验数字或文献；术语统一（如 PL / PL*、Hessian、saddle）。
4. 中文为主；公式一律 LaTeX（`$...$` / `$$...$$`），避免 Unicode 数学符号。
5. 将「## 定理：引理 1」类混乱标题规范为「### 引理 1：…」或用户要求的编号形式。
6. 压缩对话口语与重复工具输出，保留数学实质。"""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$", text, flags=re.I)
    if m:
        return m.group(1).strip()
    return text


def _looks_like_markdown(text: str) -> bool:
    return bool(text.strip()) and ("#" in text or "##" in text or len(text) > 80)


async def polish_export_markdown(
    *,
    title: str,
    markdown: str,
    instructions: str,
) -> tuple[str, bool]:
    """按用户要求调用 LLM 润色导出 Markdown。返回 (结果, 是否已应用 AI)。"""
    instructions = (instructions or "").strip()
    if not instructions:
        return markdown, False

    user_prompt = (
        f"论文标题：{title or '研究报告'}\n\n"
        f"润色要求：\n{instructions}\n\n"
        f"草稿 Markdown：\n{markdown}"
    )

    try:
        client = get_deepseek_client()
        content, _, _ = await client.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            reasoning_effort="high",
            enable_thinking=False,
            max_tokens=16_384,
        )
        polished = _strip_code_fence((content or "").strip())
        if _looks_like_markdown(polished):
            return polished, True
        logger.warning("AI 润色输出不像 Markdown，回退原稿")
    except Exception as exc:
        logger.warning("导出 AI 润色失败，回退原稿: %s", exc)

    return markdown, False
