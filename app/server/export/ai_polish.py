# 导出前 AI 整理：把会话/定理草稿整理为课题工作笔记（非代写论文）。

from __future__ import annotations

import logging
import re

from server.llm.client import get_deepseek_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 产品定位：导出 = 带走推导要点 / 定理清单 / 实验对照备忘，便于继续科研。
# 不是代写可投稿论文。前端预设与下列常量同步。
# ---------------------------------------------------------------------------

PRESET_RESEARCH_NOTES = """将草稿整理为「课题工作笔记」Markdown，供自己或协作方继续推进理论/实验。

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

文风：清晰、可执行的工作笔记；公式 $...$ / $$...$$；禁止编造草稿没有的定理、数值、文献。"""

PRESET_THEOREM_CATALOG = """将草稿整理为「定理—引理汇编」Markdown（便于核对主张），**不要**写成论文。

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

PRESET_THEORY_BRIEF = """输出「理论要点速览」工作页（便于快速对齐，非投稿摘要）：

# 标题
## 一句话主张
## 关键结论一览（表格或短列表：名称 → 一句话 → 状态）
## 关键假设（列表）
## 开放问题 / 下一步（若有，否则省略）

不要展开完整证明；不要编造草稿没有的结果；不要写成 Abstract + 贡献列表的投稿前页。"""

PRESET_EXPERIMENT_MEMO = """整理为「理论—实验对照备忘」（实验顾问笔记，非实验论文）：

# 标题
## 待检验的理论主张
## 已有数据摘要（数值必须来自草稿）
## 与理论对照（支持 / 反驳 / 不确定）
## 缺数清单
## 下一步实验建议

无实验内容时明确写「草稿未含实验数据」并缩短全文。禁止编造指标；不要写成可投稿实验报告体例。"""

# 兼容旧前端/脚本仍传 arxiv_theory 等 id
PRESET_ARXIV_THEORY = PRESET_RESEARCH_NOTES
PRESET_ABSTRACT_BRIEF = PRESET_THEORY_BRIEF
PRESET_EXPERIMENT_REPORT = PRESET_EXPERIMENT_MEMO

# 默认 = 课题工作笔记
PAPER_FORMAT_INSTRUCTIONS = PRESET_RESEARCH_NOTES

EXPORT_PRESETS: dict[str, str] = {
    "research_notes": PRESET_RESEARCH_NOTES,
    "theorem_catalog": PRESET_THEOREM_CATALOG,
    "theory_brief": PRESET_THEORY_BRIEF,
    "experiment_memo": PRESET_EXPERIMENT_MEMO,
    # 旧 id → 新文案
    "arxiv_theory": PRESET_RESEARCH_NOTES,
    "abstract_brief": PRESET_THEORY_BRIEF,
    "experiment_report": PRESET_EXPERIMENT_MEMO,
}

_SYSTEM_PROMPT = """你是言晖科研助手的「笔记整理员」。把用户草稿整理成**清晰可执行的课题工作笔记**（Markdown），方便继续推导、审稿核对或设计实验。

硬性规则：
1. **不是写论文**：禁止改写成可投稿论文 / 会议短文 / arXiv 投稿体例；不要虚构 Abstract、贡献列表、参考文献凑数。
2. 只输出 Markdown 正文（以 `#` 标题开头）；不要用 ``` 围栏包全文；不要附「改动说明」。
3. 严格按用户「整理要求」的结构输出；**无内容的节整节删除**，不要保留空壳标题。
4. 忠实草稿：不捏造定理、证明步骤、实验数字或文献。
5. 中文为主；公式一律 LaTeX（`$...$` / `$$...$$`），避免 Unicode 数学符号。
6. 将混乱标题规范为清晰的「### 引理 1：…」等形式。
7. 压缩对话口语与重复工具输出，保留数学与实验实质。"""


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
    """按用户要求调用 LLM 整理导出 Markdown。返回 (结果, 是否已应用 AI)。"""
    instructions = (instructions or "").strip()
    if not instructions:
        return markdown, False

    user_prompt = (
        f"笔记标题：{title or '课题笔记'}\n\n"
        f"整理要求：\n{instructions}\n\n"
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
        logger.warning("AI 整理输出不像 Markdown，回退原稿")
    except Exception as exc:
        logger.warning("导出 AI 整理失败，回退原稿: %s", exc)

    return markdown, False
