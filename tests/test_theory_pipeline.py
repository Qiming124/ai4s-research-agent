"""Theory 推导闭环：路由、白名单、结构化记忆、抽取、验证。"""

import json

import pytest

from server.agents.config import get_agent_default_whitelist
from server.config import Settings
from server.graph.router import classify_intent
from server.graph.theory_pipeline import (
    extract_loss_expression,
    run_sympy_verification,
)
from server.memory.structured.extract import extract_structured_entries
from server.memory.structured.injection import (
    build_structured_augmented_prompt,
    format_structured_context,
)
from server.memory.structured.store import StructuredMemoryStore
from server.mcp.whitelist import filter_openai_tools, resolve_whitelist_patterns


def test_mode_math_routes_to_theory():
    agent, reason = classify_intent("任意问题", mode="math")
    assert agent == "theory"
    assert reason == "mode=math"


def test_theory_default_whitelist_includes_sympy_rag_and_web_search():
    patterns = get_agent_default_whitelist("theory")
    assert "sympy__*" in patterns
    assert "rag__*" in patterns
    assert "web_search__*" in patterns


def test_theory_whitelist_from_json(tmp_path):
    whitelist_file = tmp_path / "whitelist.json"
    whitelist_file.write_text(
        json.dumps({"global": [], "agents": {"theory": ["sympy__*"]}}),
        encoding="utf-8",
    )
    settings = Settings(
        deepseek_api_key="sk-test",
        mcp_tool_whitelist_path=str(whitelist_file),
    )
    patterns = resolve_whitelist_patterns(settings, "theory")
    assert "sympy__*" in patterns


def test_extract_structured_entries():
    content = """
## 引理 1
**陈述**：梯度为零。
**证明**：由定义可得。

## 定理 1
**陈述**：Hessian 正定则局部极小。
**证明**：Taylor 展开。
"""
    entries = extract_structured_entries(content)
    assert len(entries) == 2
    assert entries[0]["kind"] == "theorem"
    assert "引理 1" in entries[0]["title"]


def test_format_structured_context():
    text = format_structured_context(
        [{"kind": "theorem", "title": "引理 1", "body": "内容"}]
    )
    assert "引理 1" in text
    assert "内容" in text


def test_build_structured_augmented_prompt(tmp_path):
    db_path = tmp_path / "sessions.db"
    settings = Settings(
        deepseek_api_key="sk-test",
        session_db_path=str(db_path),
        structured_memory_agents="theory",
    )
    store = StructuredMemoryStore(str(db_path))
    store.create_entry(
        session_id="s1",
        kind="theorem",
        title="引理 1",
        body="测试引理",
    )
    prompt = build_structured_augmented_prompt(
        "base",
        "s1",
        "theory",
        settings,
    )
    assert "测试引理" in prompt
    assert "base" in prompt


def test_extract_loss_expression():
    text = "损失函数为 $$L = \\theta**2 + 1$$"
    expr = extract_loss_expression(text)
    assert expr is not None


@pytest.mark.asyncio
async def test_run_sympy_verification_with_prior_tool_call():
    from shared.schemas import PersistedToolCall

    records = [
        PersistedToolCall(
            id="1",
            name="sympy__differentiate",
            arguments="{}",
            status="success",
        )
    ]
    result = await run_sympy_verification(None, "content", records)  # type: ignore[arg-type]
    assert result["status"] == "pass"
