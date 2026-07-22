"""提示词优化器单元测试（无 LLM）。"""

from server.llm.prompt_optimizer import _fallback_result, _parse_llm_result
from server.llm.prompt_test_cases import get_test_case, list_test_cases
from server.llm.prompt_templates import list_templates


def test_list_templates():
    tpls = list_templates()
    assert len(tpls) == 4


def test_research_test_cases():
    cases = list_test_cases()
    assert len(cases) >= 5
    case = get_test_case("imrad_results")
    assert case is not None
    assert "82%" in case["raw_prompt"]


def test_fallback_result_has_all_styles():
    result = _fallback_result("分析梯度", "Math 模式", "更专业")
    assert len(result["variants"]) == 4
    assert result["recommended_prompt"]
    assert result["recommended_style_id"]


def test_parse_llm_json():
    raw = """{
      "variants": [
        {
          "style_id": "imrad",
          "prompt": "撰写 Results 段落…",
          "scores": {"clarity": 8, "specificity": 9, "verifiability": 7, "structure": 8},
          "highlights": ["IMRaD"]
        }
      ],
      "recommended_style_id": "imrad",
      "rationale": "适合结果描述"
    }"""
    result = _parse_llm_result(raw, text="写结果", context="", goal="")
    assert result["ai_applied"] is True
    assert result["variants"][0]["style_name_zh"] == "IMRaD 分节写作"
