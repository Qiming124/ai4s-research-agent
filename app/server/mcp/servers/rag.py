# =============================================================================
# MCP Server：RAG 按需检索（按 session / project 隔离）。
# =============================================================================

from __future__ import annotations

import json
import sys
from pathlib import Path

# 保证 stdio 子进程可 import server.*（即使父进程未设 PYTHONPATH）
# rag.py → servers → mcp → server → app ；须把 app/ 加入 path，勿用 parents[2]（会把 server/ 顶掉真实 mcp 包）
_APP_DIR = Path(__file__).resolve().parents[3]
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from mcp.server.fastmcp import FastMCP

from server.config import get_settings  # noqa: E402 — fail fast if import broken

mcp = FastMCP("rag")


def _retrieve(
    query: str,
    top_k: int,
    session_id: str,
    project_id: str = "",
) -> str:
    from server.memory.rag.retrieval import retrieve_for_query

    settings = get_settings()
    if not settings.enable_rag:
        return json.dumps(
            {"error": "RAG 未启用。请在 conf/.env 中设置 ENABLE_RAG=true"},
            ensure_ascii=False,
        )

    session_id = (session_id or "").strip()
    if not session_id:
        return json.dumps(
            {
                "error": "缺少 session_id。请传入当前对话的 session_id，不要使用字面量 default。",
            },
            ensure_ascii=False,
        )
    if session_id == "default":
        return json.dumps(
            {
                "error": "session_id=default 无效。请使用当前聊天会话 UUID。",
                "hint": "从对话上下文取真实 session_id，并可选传入 project_id。",
            },
            ensure_ascii=False,
        )

    pid = (project_id or "").strip() or None
    snippets = retrieve_for_query(
        query,
        settings,
        session_id=session_id,
        top_k=top_k,
        project_id=pid,
    )
    return json.dumps(
        {
            "query": query,
            "session_id": session_id,
            "project_id": pid,
            "count": len(snippets),
            "results": [
                {
                    "doc_id": s.doc_id,
                    "title": s.title,
                    "source": s.source,
                    "content": s.content,
                    "score": s.score,
                }
                for s in snippets
            ],
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def retrieve(
    query: str,
    top_k: int = 4,
    session_id: str = "",
    project_id: str = "",
) -> str:
    """从当前课题/会话 RAG 向量库检索与 query 相关的文档片段。

    Args:
        query: 检索问题或关键词
        top_k: 返回片段数量（默认 4）
        session_id: 当前对话 session_id（必填，禁止传 default）
        project_id: 可选课题 ID；省略则由会话反查
    """
    return _retrieve(query, top_k, session_id, project_id=project_id)


def main() -> None:
    # 启动即验证配置可导入
    get_settings()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
