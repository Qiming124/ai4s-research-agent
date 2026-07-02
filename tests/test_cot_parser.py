"""结构化思维链解析器单元测试。"""

from server.llm.cot_parser import parse_cot_sections
from server.llm.cot_prompt import apply_cot_prompt, STRUCTURED_COT_SUFFIX_STANDARD
from server.llm.prompts import DEFAULT_SYSTEM_PROMPT, THEORY_AGENT_PROMPT


def test_parse_cot_sections_three_parts():
    content = """## 问题分析
用户问的是梯度下降。

## 推理过程
一阶条件给出驻点。

## 结论
局部极小需 Hessian 正定。
"""
    steps = parse_cot_sections(content)
    assert len(steps) == 3
    assert steps[0].title == "问题分析"
    assert "梯度下降" in steps[0].body
    assert steps[2].title == "结论"


def test_parse_cot_sections_empty_without_headers():
    assert parse_cot_sections("纯文本无标题") == []


def test_apply_cot_prompt_skips_theory():
    base = THEORY_AGENT_PROMPT
    assert apply_cot_prompt(base, "standard", "theory") == base
    assert STRUCTURED_COT_SUFFIX_STANDARD not in base


def test_apply_cot_prompt_injects_for_general():
    result = apply_cot_prompt(DEFAULT_SYSTEM_PROMPT, "strict", "general")
    assert "问题分析" in result
    assert result.startswith(DEFAULT_SYSTEM_PROMPT)


def test_apply_cot_prompt_off():
    assert apply_cot_prompt(DEFAULT_SYSTEM_PROMPT, "off", "general") == DEFAULT_SYSTEM_PROMPT
