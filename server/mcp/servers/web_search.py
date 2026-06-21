# MCP Server：Web 搜索（DuckDuckGo HTML + Instant Answer 备用）。

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import quote_plus

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web_search")
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


async def _http_get(url: str, *, params: dict | None = None) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        headers=_HTTP_HEADERS,
    ) as client:
        return await client.get(url, params=params)


def _strip_tags(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _parse_ddg_html(html: str, max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    # 新版 / 经典 HTML 结构
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

    # 备用：links_main links_deep
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


@mcp.tool()
async def search(query: str, max_results: int = 5) -> str:
    """搜索互联网获取最新信息。

    Args:
        query: 搜索关键词
        max_results: 返回结果数量（1-10）
    """
    max_results = max(1, min(max_results, 10))
    errors: list[str] = []

    for name, coro in (
        ("duckduckgo_html", _search_ddg_html(query, max_results)),
        ("duckduckgo_instant", _search_ddg_instant(query, max_results)),
        ("wikipedia", _search_wikipedia(query, max_results)),
    ):
        try:
            results = await coro
            if results:
                return json.dumps(
                    {"query": query, "source": name, "results": results},
                    ensure_ascii=False,
                    indent=2,
                )
        except httpx.HTTPError as exc:
            errors.append(f"{name}: {_format_http_error(exc)}")
        except Exception as exc:
            errors.append(f"{name}: {_format_http_error(exc)}")

    return json.dumps(
        {
            "query": query,
            "results": [],
            "message": "未找到结果或搜索服务不可达",
            "errors": errors,
        },
        ensure_ascii=False,
        indent=2,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
