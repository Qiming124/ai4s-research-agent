# =============================================================================
# 终端 CLI 客户端。
#
# 职责：通过 HTTP 与 FastAPI Server 通信，提供交互式多轮对话体验。
#       支持流式打印 reasoning（思考过程）与最终回答。
#
# 架构位置：用户终端 → 本 CLI → POST /v1/chat/stream（SSE）→ server/api/chat.py
#
# 依赖：
#     httpx          — 异步 HTTP 客户端
#     httpx-sse      — 消费 SSE 流，逐行解析 data: {...}
#     rich           — 终端美化输出（颜色、面板、Live 原地刷新）
#     prompt_toolkit — 多行输入 + 命令历史（上下箭头翻阅）
#
# 启动：
#     python -m client.cli
#     python -m client.cli --server http://127.0.0.1:8000 --session my-work
#
# Debug：
#     - Connection refused  → Server 未启动或 --server 地址不对
#     - 401/502             → Server 端 DeepSeek API 问题，查 Server 日志
#     - asyncio RuntimeError → 已修复——用 prompt_async 替代 prompt
# =============================================================================

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


# ── 命令行参数解析 ────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    # 解析命令行参数，返回 Namespace 含 server / session / show_reasoning / mode 属性。
    parser = argparse.ArgumentParser(
        description="AI4S 科研助手 CLI — 与 DeepSeek Agent Server 对话",
    )
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Server 地址 (默认: {DEFAULT_SERVER})")
    parser.add_argument("--session", default=None, help="会话 ID；不指定则自动生成 UUID")
    parser.add_argument(
        "--show-reasoning",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否显示模型 thinking 过程 (默认开启)",
    )
    parser.add_argument(
        "--mode", choices=["chat", "math"], default="chat",
        help="对话模式：chat=通用，math=数学推导 (预留)",
    )
    return parser.parse_args()


# ── Server 通信 ─────────────────────────────────────────────

async def check_server_health(client: httpx.AsyncClient) -> dict[str, Any]:
    # 调用 GET /health 确认 server 可连。失败抛 httpx.ConnectError。
    response = await client.get("/health")
    response.raise_for_status()
    return response.json()


async def clear_session(client: httpx.AsyncClient, session_id: str) -> None:
    # 调用 DELETE /v1/sessions/{id} 清空当前会话历史。
    response = await client.delete(f"/v1/sessions/{session_id}")
    response.raise_for_status()
    console.print(f"[green]会话 {session_id} 已清空[/green]")


async def get_session_history(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    # 调用 GET /v1/sessions/{id} 获取历史消息。
    # 返回消息列表；404 时返回空列表。
    response = await client.get(f"/v1/sessions/{session_id}")
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json().get("messages", [])


# ── 终端显示 ─────────────────────────────────────────────────

def build_display_text(reasoning: str, content: str, *, show_reasoning: bool) -> Text:
    # 将思考过程与回答组装成 rich Text 对象，用于 Live 实时刷新。
    #
    # 参数：
    #     reasoning      — 已累积的思考过程文本
    #     content        — 已累积的回答文本
    #     show_reasoning — 是否显示思考过程
    #
    # 返回 rich.Text：思考过程灰色、回答绿色。
    text = Text()
    if show_reasoning and reasoning:
        text.append("【推理过程】\n", style="bold dim cyan")
        text.append(reasoning, style="dim")
        text.append("\n\n")
    if content:
        text.append("【回答】\n", style="bold green")
        text.append(content)
    return text


# ── SSE 流式对话 ─────────────────────────────────────────────

async def stream_chat(
    client: httpx.AsyncClient, session_id: str, message: str, *, show_reasoning: bool,
) -> tuple[str, str]:
    # 调用 POST /v1/chat/stream，消费 SSE 事件流并实时显示在终端。
    #
    # 参数：
    #     client         — httpx 异步客户端
    #     session_id     — 当前会话 ID
    #     message        — 用户输入文本
    #     show_reasoning — 是否显示思考过程
    #
    # 返回 (reasoning, content) 完整累积文本。
    #
    # 实现：
    #     1. httpx-sse 建 POST 连接
    #     2. 逐行解析 SSE data 事件，区分 reasoning/content/done/error
    #     3. rich.Live 原地刷新终端区域
    #     4. 收到 done 后退出
    payload = {"message": message, "session_id": session_id}
    reasoning_parts: list[str] = []
    content_parts: list[str] = []

    with Live(console=console, refresh_per_second=12, transient=False) as live:
        async with aconnect_sse(
            client, "POST", "/v1/chat/stream", json=payload,
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
                    sid = data.get("session_id")
                    if sid:
                        pass  # 已在 run_cli 打印
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

                live.update(
                    Panel(
                        build_display_text(
                            "".join(reasoning_parts), "".join(content_parts),
                            show_reasoning=show_reasoning,
                        ),
                        title="Assistant",
                        border_style="blue",
                    )
                )

    return "".join(reasoning_parts), "".join(content_parts)


# ── 用户输入处理 ─────────────────────────────────────────────

async def read_multiline_input(session: PromptSession) -> str:
    # 读取用户输入，支持单行与多行模式。
    #
    # 单行：直接输入回车发送
    # 多行：第一行末尾 \ 回车 → 续行模式，空行结束
    #
    # 用 prompt_async 而非 prompt：CLI 主循环已在事件循环中，
    # prompt() 内部 asyncio.run() 会导致 RuntimeError。
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


# ── 主循环 ───────────────────────────────────────────────────

async def run_cli(args: argparse.Namespace) -> None:
    # CLI 主入口。
    #
    # 流程：
    #     1. 确定 session_id
    #     2. 连接 Server + 健康检查
    #     3. 交互主循环：读入 → 处理内置命令 → 发起流式对话
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
        try:
            health = await check_server_health(client)
            console.print(
                f"[green]已连接[/green] model={health.get('model')} "
                f"reasoning={health.get('reasoning_effort')}"
            )
        except httpx.ConnectError:
            console.print(
                f"[red]无法连接 Server: {base_url}[/red]\n"
                "请先启动: uvicorn server.main:app --host 0.0.0.0 --port 8000"
            )
            sys.exit(1)
        except httpx.HTTPStatusError as exc:
            console.print(f"[red]Server 返回错误: {exc}[/red]")
            sys.exit(1)

        prompt_session = PromptSession(history=InMemoryHistory())

        while True:
            try:
                user_input = await read_multiline_input(prompt_session)
            except (EOFError, KeyboardInterrupt):
                console.print("\n[yellow]再见！[/yellow]")
                break

            if not user_input:
                continue

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

            console.print()
            try:
                await stream_chat(client, session_id, user_input, show_reasoning=args.show_reasoning)
            except httpx.ConnectError:
                console.print("[red]连接中断，请确认 Server 是否仍在运行[/red]")
            except httpx.HTTPStatusError as exc:
                console.print(f"[red]请求失败: {exc.response.status_code} {exc.response.text}[/red]")
            console.print()


# ── 入口 ─────────────────────────────────────────────────────

def main() -> None:
    # 程序入口：解析命令行参数 → asyncio.run() 启动异步主循环。
    # 同时作为 pyproject.toml 中 research-agent-cli 命令的入口函数。
    args = parse_args()
    asyncio.run(run_cli(args))


if __name__ == "__main__":
    main()
