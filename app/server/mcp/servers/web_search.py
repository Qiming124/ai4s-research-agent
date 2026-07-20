# =============================================================================
# MCP Server：Web 搜索（Tavily / DuckDuckGo / Wikipedia）。
#
# 职责：
#     1. web_search 工具：TAVILY_API_KEY 优先，否则 DuckDuckGo HTML
#     2. wikipedia_summary 备用百科摘要
#     3. 统一 JSON 结果格式与超时控制
#
# 架构位置：
#     - 被调用：MCP Client stdio 子进程
#     - 调用：httpx、可选 Tavily API
#
# 阅读提示：
#     - 新人先看 web_search 分支逻辑
#
# Debug：
#     - 无 Tavily → 环境变量 TAVILY_API_KEY 未设，走 DuckDuckGo
#     - DuckDuckGo 空 → HTML 结构变化或 IP 限流
# =============================================================================

from __future__ import annotations

import asyncio
import json
import os
import re
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web_search")

_HTTP_TIMEOUT = float(os.environ.get("WEB_SEARCH_HTTP_TIMEOUT", "8"))
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _http_proxy() -> str | None:
    return (
        os.environ.get("WEB_SEARCH_HTTP_PROXY", "").strip()
        or os.environ.get("HTTPS_PROXY", "").strip()
        or os.environ.get("HTTP_PROXY", "").strip()
        or None
    )


def _project_root() -> Path:
    # app/server/mcp/servers/web_search.py → 仓库根
    return Path(__file__).resolve().parents[4]


def _load_tavily_from_env_file() -> str:
    """MCP stdio 子进程可能未继承 TAVILY_API_KEY，直接从 conf/.env 读取。"""
    candidates = [
        os.environ.get("ENV_FILE", "").strip(),
        str(_project_root() / "conf" / ".env"),
        str(_project_root() / ".env"),
    ]
    for env_path in candidates:
        if not env_path:
            continue
        path = Path(env_path)
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, _, value = stripped.partition("=")
                if key.strip() == "TAVILY_API_KEY":
                    return value.strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def _tavily_api_key() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if key:
        return key
    return _load_tavily_from_env_file()


async def _http_get(url: str, *, params: dict | None = None) -> httpx.Response:
    proxy = _http_proxy()
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        follow_redirects=True,
        headers=_HTTP_HEADERS,
        proxy=proxy,
        trust_env=True,
    ) as client:
        return await client.get(url, params=params)


def _strip_tags(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _parse_ddg_html(html: str, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    for block in html.split('class="result__body"'):
        if len(results) >= max_results:
            break
        m = re.search(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            block,
            re.DOTALL,
        )
        if not m:
            continue
        link, title_raw = m.group(1), m.group(2)
        title = _strip_tags(title_raw)
        snippet = ""
        sm = re.search(r'class="result__snippet"[^>]*>(.*?)</', block, re.DOTALL)
        if sm:
            snippet = _strip_tags(sm.group(1))
        if title:
            results.append({"title": title, "url": link, "snippet": snippet})

    if not results:
        for m in re.finditer(
            r'class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        ):
            if len(results) >= max_results:
                break
            title = _strip_tags(m.group(2))
            if title:
                results.append({
                    "title": title,
                    "url": m.group(1),
                    "snippet": "",
                })

    return results


async def _search_tavily(query: str, max_results: int) -> list[dict[str, str]]:
    api_key = _tavily_api_key()
    if not api_key:
        return []

    proxy = _http_proxy()
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, proxy=proxy, trust_env=True) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results: list[dict[str, str]] = []
    for item in data.get("results", []):
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        snippet = (item.get("content") or item.get("snippet") or "").strip()
        if title or url:
            results.append({"title": title or url, "url": url, "snippet": snippet[:500]})
    return results[:max_results]


async def _search_ddg_html(query: str, max_results: int) -> list[dict[str, str]]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    resp = await _http_get(url)
    resp.raise_for_status()
    return _parse_ddg_html(resp.text, max_results)


async def _search_wikipedia(query: str, max_results: int) -> list[dict[str, str]]:
    resp = await _http_get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_results,
            "format": "json",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    results: list[dict[str, str]] = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        if not title:
            continue
        snippet = _strip_tags(item.get("snippet", ""))
        url = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _format_http_error(exc: Exception) -> str:
    msg = str(exc).strip()
    return f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__


async def _search_ddg_instant(query: str, max_results: int) -> list[dict[str, str]]:
    resp = await _http_get(
        "https://api.duckduckgo.com/",
        params={
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    abstract = (data.get("Abstract") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    if abstract and abstract_url:
        results.append({
            "title": data.get("Heading") or query,
            "url": abstract_url,
            "snippet": abstract[:500],
        })

    def collect_topics(topics: list) -> None:
        for item in topics:
            if len(results) >= max_results:
                return
            if "Topics" in item:
                collect_topics(item["Topics"])
                continue
            text = (item.get("Text") or "").strip()
            url = (item.get("FirstURL") or "").strip()
            if text and url:
                results.append({"title": text[:120], "url": url, "snippet": text})

    collect_topics(data.get("RelatedTopics") or [])
    return results[:max_results]


def _setup_hint() -> str:
    if _tavily_api_key():
        return ""
    return (
        "未配置 TAVILY_API_KEY。国内网络通常无法访问 DuckDuckGo/Wikipedia，"
        "请在 conf/.env 添加 TAVILY_API_KEY（免费注册 https://tavily.com）。"
        "若已有代理，可设置 HTTPS_PROXY 或 WEB_SEARCH_HTTP_PROXY。"
    )


@mcp.tool()
async def search(query: str, max_results: int = 5) -> str:
    """搜索互联网获取最新信息。

    Args:
        query: 搜索关键词
        max_results: 返回结果数量（1-10）
    """
    max_results = max(1, min(max_results, 10))
    errors: list[str] = []
    hint = _setup_hint()
    if hint:
        errors.append(hint)
    has_tavily_key = bool(_tavily_api_key())

    try:
        tavily_results = await asyncio.wait_for(
            _search_tavily(query, max_results),
            timeout=_HTTP_TIMEOUT + 2,
        )
        if tavily_results:
            return json.dumps(
                {"query": query, "source": "tavily", "results": tavily_results},
                ensure_ascii=False,
                indent=2,
            )
    except asyncio.TimeoutError:
        errors.append("tavily: TimeoutError")
    except httpx.HTTPError as exc:
        errors.append(f"tavily: {_format_http_error(exc)}")
    except Exception as exc:
        errors.append(f"tavily: {_format_http_error(exc)}")

    # 已配置 Tavily 时不再尝试 DuckDuckGo/Wikipedia（国内通常超时 ~30s）
    if has_tavily_key:
        payload: dict[str, object] = {
            "query": query,
            "results": [],
            "message": "Tavily 搜索未返回结果",
            "errors": errors,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    for name, coro in (
        ("duckduckgo_html", _search_ddg_html(query, max_results)),
        ("duckduckgo_instant", _search_ddg_instant(query, max_results)),
        ("wikipedia", _search_wikipedia(query, max_results)),
    ):
        try:
            results = await asyncio.wait_for(coro, timeout=_HTTP_TIMEOUT + 2)
            if results:
                return json.dumps(
                    {"query": query, "source": name, "results": results},
                    ensure_ascii=False,
                    indent=2,
                )
        except asyncio.TimeoutError:
            errors.append(f"{name}: ConnectTimeout")
        except httpx.HTTPError as exc:
            errors.append(f"{name}: {_format_http_error(exc)}")
        except Exception as exc:
            errors.append(f"{name}: {_format_http_error(exc)}")

    payload: dict[str, object] = {
        "query": query,
        "results": [],
        "message": "未找到结果或搜索服务不可达",
        "errors": errors,
    }
    if hint:
        payload["setup_hint"] = hint
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
