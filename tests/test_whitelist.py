"""MCP 工具白名单过滤测试。"""

from server.config import Settings
from server.mcp.whitelist import filter_openai_tools, resolve_whitelist_patterns


def _sample_tools() -> list[dict]:
    return [
        {"type": "function", "function": {"name": "filesystem__read_file"}},
        {"type": "function", "function": {"name": "arxiv__search_papers"}},
        {"type": "function", "function": {"name": "web_search__search"}},
        {"type": "function", "function": {"name": "sympy__simplify_expression"}},
    ]


def test_literature_whitelist():
    settings = Settings(
        deepseek_api_key="sk-test",
        mcp_tool_whitelist="",
        mcp_tool_whitelist_path="",
    )
    patterns = resolve_whitelist_patterns(settings, "literature")
    assert "arxiv__*" in patterns or "*" in patterns

    filtered = filter_openai_tools(_sample_tools(), settings, "literature")
    names = {t["function"]["name"] for t in filtered}
    assert "arxiv__search_papers" in names
    assert "filesystem__read_file" not in names


def test_theory_tool_whitelist():
    settings = Settings(
        deepseek_api_key="sk-test",
        mcp_tool_whitelist="",
        mcp_tool_whitelist_path="",
    )
    filtered = filter_openai_tools(_sample_tools(), settings, "theory")
    names = {t["function"]["name"] for t in filtered}
    assert names == {"sympy__simplify_expression", "web_search__search"}
