"""
终端 CLI 客户端。

职责：
    通过 HTTP 与 FastAPI server 通信，提供交互式多轮对话体验，
    支持流式显示 reasoning（thinking）与最终回答。

架构位置：
    用户终端 → 本 CLI → server/api/chat.py (SSE)

主要依赖：
    httpx        — 异步 HTTP 客户端（类似 C++ 的 libcurl wrapper）
    httpx-sse    — 消费 Server-Sent Events 流
    rich         — 终端美化输出（颜色、Live 刷新）
    prompt_toolkit — 多行输入、命令历史

启动方式：
    python -m client.cli
    python -m client.cli --server http://127.0.0.1:8000 --session my-work

Debug：
    - Connection refused：server 未启动或 --server 地址错误
    - 401/502：server 端 DeepSeek API 配置问题，查看 server 日志
    - Ctrl+C：捕获 KeyboardInterrupt 优雅退出
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

import httpx
from httpx_sse import aconnect_sse
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

# 默认 server 地址
DEFAULT_SERVER = "http://127.0.0.1:8000"

console = Console()


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="AI4S 科研助手 CLI — 与 DeepSeek Agent Server 对话",
    )
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"Agent Server 地址 (默认: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--session",
        default=None,
        help="会话 ID；不指定则自动生成 UUID，便于固定同一研究主题的多轮对话",
    )
    parser.add_argument(
        "--show-reasoning",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否显示模型的 thinking/reasoning 过程 (默认: 开启)",
    )
    parser.add_argument(
        "--mode",
        choices=["chat", "math"],
        default="chat",
        help="对话模式：chat=通用科研助手，math=形式化数学推导 (Phase 1 预留，需 server 支持)",
    )
    return parser.parse_args()


async def check_server_health(client: httpx.AsyncClient) -> dict[str, Any]:
    """
    调用 GET /health 确认 server 可用。

    Raises:
        httpx.ConnectError: 无法连接 server
    """
    response = await client.get("/health")
    response.raise_for_status()
    return response.json()


async def clear_session(client: httpx.AsyncClient, session_id: str) -> None:
    """调用 DELETE /v1/sessions/{id} 清空会话历史。"""
    response = await client.delete(f"/v1/sessions/{session_id}")
    response.raise_for_status()
    console.print(f"[green]会话 {session_id} 已清空[/green]")


async def get_session_history(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    """调用 GET /v1/sessions/{id} 获取历史消息。"""
    response = await client.get(f"/v1/sessions/{session_id}")
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json().get("messages", [])


def build_display_text(
    reasoning: str,
    content: str,
    *,
    show_reasoning: bool,
) -> Text:
    """
    构造 rich Text 对象用于 Live 刷新显示。

    reasoning 用 dim 样式（灰色），content 用正常白色，便于区分 thinking 与回答。
    """
    text = Text()
    if show_reasoning and reasoning:
        text.append("【推理过程】\n", style="bold dim cyan")
        text.append(reasoning, style="dim")
        text.append("\n\n")
    if content:
        text.append("【回答】\n", style="bold green")
        text.append(content)
    return text


async def stream_chat(
    client: httpx.AsyncClient,
    session_id: str,
    message: str,
    *,
    show_reasoning: bool,
) -> tuple[str, str]:
    """
    调用 POST /v1/chat/stream，消费 SSE 事件并实时打印。

    httpx-sse 的 aconnect_sse 类似 C++ 中逐行读取 chunked HTTP response。

    Returns:
        (reasoning, content) 完整累积文本
    """
    payload = {"message": message, "session_id": session_id}
    reasoning_parts: list[str] = []
    content_parts: list[str] = []

    # Live 组件会原地刷新终端区域，避免流式输出刷屏
    with Live(console=console, refresh_per_second=12, transient=False) as live:
        async with aconnect_sse(
            client,
            "POST",
            "/v1/chat/stream",
            json=payload,
            timeout=httpx.Timeout(600.0, connect=10.0),
        ) as event_source:
            async for sse in event_source.aiter_sse():
                if not sse.data:
                    continue

                try:
                    data = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue

                event_type = data.get("type")

                if event_type == "meta":
                    # 服务端确认的 session_id（通常与客户端一致）
                    sid = data.get("session_id")
                    if sid:
                        pass  # 已在启动时打印
                    continue

                if event_type == "reasoning":
                    reasoning_parts.append(data.get("content", ""))
                elif event_type == "content":
                    content_parts.append(data.get("content", ""))
                elif event_type == "error":
                    live.update(Panel(f"[red]错误: {data.get('content')}[/red]"))
                    return "".join(reasoning_parts), "".join(content_parts)
                elif event_type == "done":
                    usage = data.get("usage")
                    if usage and console.is_terminal:
                        console.print(f"[dim]Token 用量: {usage}[/dim]")
                    break

                # 每次收到新 chunk 都刷新 Live 面板
                live.update(
                    Panel(
                        build_display_text(
                            "".join(reasoning_parts),
                            "".join(content_parts),
                            show_reasoning=show_reasoning,
                        ),
                        title="Assistant",
                        border_style="blue",
                    )
                )

    return "".join(reasoning_parts), "".join(content_parts)


async def read_multiline_input(session: PromptSession) -> str:
    """
    读取用户输入，支持多行（空行结束）与单行模式。

    单行：直接输入回车发送
    多行：第一行后输入 \\ 并回车继续，空行结束

    注意：必须在 async 函数内使用 prompt_async，不能用 prompt()。
    prompt() 内部会 asyncio.run()，而 CLI 主循环已在事件循环中，会触发：
        RuntimeError: asyncio.run() cannot be called from a running event loop
    """
    first_line = await session.prompt_async("You> ")
    if not first_line.endswith("\\"):
        return first_line.rstrip("\\").strip()

    lines = [first_line.rstrip("\\").rstrip()]
    while True:
        line = await session.prompt_async("...> ")
        if line == "":
            break
        lines.append(line.rstrip("\\").rstrip())
    return "\n".join(lines).strip()


async def run_cli(args: argparse.Namespace) -> None:
    """CLI 主循环。"""
    session_id = args.session or str(uuid.uuid4())
    base_url = args.server.rstrip("/")

    console.print(Panel.fit(
        "[bold]AI4S 科研助手 CLI[/bold]\n"
        f"Server: {base_url}\n"
        f"Session: {session_id}\n"
        "命令: /clear 清空会话 | /history 查看历史 | exit/quit 退出",
        border_style="cyan",
    ))

    async with httpx.AsyncClient(base_url=base_url) as client:
        # 启动时检查 server 健康状态
        try:
            health = await check_server_health(client)
            console.print(
                f"[green]已连接[/green] model={health.get('model')} "
                f"reasoning={health.get('reasoning_effort')}"
            )
        except httpx.ConnectError:
            console.print(
                f"[red]无法连接 Server: {base_url}[/red]\n"
                "请先启动服务: uvicorn server.main:app --reload --host 0.0.0.0 --port 8000"
            )
            sys.exit(1)
        except httpx.HTTPStatusError as exc:
            console.print(f"[red]Server 返回错误: {exc}[/red]")
            sys.exit(1)

        # prompt_toolkit 提供行编辑与历史（上下箭头翻阅）
        prompt_session = PromptSession(history=InMemoryHistory())

        while True:
            try:
                user_input = await read_multiline_input(prompt_session)
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]再见！[/yellow]")
                break

            if not user_input:
                continue

            # 内置命令处理
            cmd = user_input.strip().lower()
            if cmd in ("exit", "quit"):
                console.print("[yellow]再见！[/yellow]")
                break
            if cmd == "/clear":
                await clear_session(client, session_id)
                continue
            if cmd == "/history":
                messages = await get_session_history(client, session_id)
                if not messages:
                    console.print("[dim]（无历史消息）[/dim]")
                else:
                    for i, msg in enumerate(messages, 1):
                        role = msg.get("role", "?")
                        content = msg.get("content", "")
                        console.print(Panel(content, title=f"{i}. {role}", border_style="dim"))
                continue

            # 发起流式对话
            console.print()
            try:
                await stream_chat(
                    client,
                    session_id,
                    user_input,
                    show_reasoning=args.show_reasoning,
                )
            except httpx.ConnectError:
                console.print("[red]连接中断，请确认 Server 是否仍在运行[/red]")
            except httpx.HTTPStatusError as exc:
                console.print(f"[red]请求失败: {exc.response.status_code} {exc.response.text}[/red]")
            console.print()


def main() -> None:
    """入口函数，供 python -m client.cli 与 research-agent-cli 脚本调用。"""
    args = parse_args()
    asyncio.run(run_cli(args))


if __name__ == "__main__":
    main()
