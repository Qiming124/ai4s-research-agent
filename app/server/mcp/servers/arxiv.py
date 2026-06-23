# MCP Server：arXiv 论文搜索与摘要。

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("arxiv")
_ARXIV_API = "https://export.arxiv.org/api/query"
_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
_HTTP_HEADERS = {"User-Agent": "AI4S-Research-Agent/1.0 (mailto:support@example.com)"}


async def _fetch_arxiv(params: dict[str, str | int]) -> ET.Element:
    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        headers=_HTTP_HEADERS,
    ) as client:
        resp = await client.get(_ARXIV_API, params=params)
        resp.raise_for_status()
        return ET.fromstring(resp.text)


@mcp.tool()
async def search_papers(query: str, max_results: int = 5) -> str:
    """搜索 arXiv 论文。

    Args:
        query: 搜索关键词（标题/摘要/作者）
        max_results: 返回论文数量（1-20）
    """
    max_results = max(1, min(max_results, 20))
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    try:
        root = await _fetch_arxiv(params)
    except httpx.HTTPError as exc:
        return json.dumps(
            {"query": query, "papers": [], "error": f"arXiv API 请求失败: {exc}"},
            ensure_ascii=False,
        )

    papers: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", _ARXIV_NS):
        arxiv_id = _extract_id(entry)
        title = (entry.findtext("atom:title", default="", namespaces=_ARXIV_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=_ARXIV_NS) or "").strip()
        authors = [
            a.findtext("atom:name", default="", namespaces=_ARXIV_NS) or ""
            for a in entry.findall("atom:author", _ARXIV_NS)
        ]
        link = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
        papers.append({
            "id": arxiv_id,
            "title": _collapse_ws(title),
            "authors": ", ".join(authors[:5]),
            "summary": _collapse_ws(summary)[:500],
            "url": link,
        })

    return json.dumps({"query": query, "papers": papers}, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_paper(arxiv_id: str) -> str:
    """获取单篇 arXiv 论文详情。

    Args:
        arxiv_id: arXiv ID，如 2301.00001 或 cs.LG/0001001
    """
    clean_id = arxiv_id.strip().replace("arxiv:", "")
    params = {"id_list": clean_id}

    try:
        root = await _fetch_arxiv(params)
    except httpx.HTTPError as exc:
        return json.dumps({"error": f"arXiv API 请求失败: {exc}"}, ensure_ascii=False)

    entry = root.find("atom:entry", _ARXIV_NS)
    if entry is None:
        return json.dumps({"error": f"未找到论文: {arxiv_id}"}, ensure_ascii=False)

    title = _collapse_ws(entry.findtext("atom:title", default="", namespaces=_ARXIV_NS) or "")
    summary = _collapse_ws(entry.findtext("atom:summary", default="", namespaces=_ARXIV_NS) or "")
    authors = [
        a.findtext("atom:name", default="", namespaces=_ARXIV_NS) or ""
        for a in entry.findall("atom:author", _ARXIV_NS)
    ]
    published = entry.findtext("atom:published", default="", namespaces=_ARXIV_NS) or ""

    return json.dumps({
        "id": clean_id,
        "title": title,
        "authors": authors,
        "published": published,
        "summary": summary,
        "url": f"https://arxiv.org/abs/{clean_id}",
    }, ensure_ascii=False, indent=2)


def _extract_id(entry: ET.Element) -> str:
    raw = entry.findtext("atom:id", default="", namespaces=_ARXIV_NS) or ""
    match = re.search(r"arxiv\.org/abs/(.+)$", raw)
    return match.group(1) if match else raw.rsplit("/", 1)[-1]


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
