"""Research Tools.

This module provides search and content processing utilities for the research agent,
using Tavily for URL discovery and fetching full webpage content.
"""

import os
import re
import httpx
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from typing_extensions import Annotated, Literal

_tavily_client: TavilyClient | None = None


def _get_tavily_client() -> TavilyClient | None:
    """按需初始化 Tavily 客户端，避免缺 key 时导入即失败。"""
    global _tavily_client
    if _tavily_client is not None:
        return _tavily_client

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    try:
        _tavily_client = TavilyClient(api_key=api_key)
    except Exception:
        _tavily_client = None
    return _tavily_client


def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch and convert webpage content to markdown.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Webpage content as markdown
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return markdownify(response.text)
    except Exception as e:
        return f"Error fetching content from {url}: {str(e)}"


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _fallback_web_search(query: str, max_results: int = 3) -> list[dict]:
    """当 Tavily 不可用时的免费搜索兜底。"""
    results: list[dict] = []

    # 1) DuckDuckGo Instant Answer（免 key）
    try:
        response = httpx.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
            timeout=12.0,
        )
        response.raise_for_status()
        data = response.json()
        abstract = data.get("AbstractText")
        if abstract:
            results.append(
                {
                    "title": data.get("Heading") or query,
                    "url": data.get("AbstractURL") or "",
                    "content": abstract,
                }
            )
        for topic in data.get("RelatedTopics", []) or []:
            if len(results) >= max_results:
                break
            if isinstance(topic, dict) and "Text" in topic:
                results.append(
                    {
                        "title": topic.get("Text", "").split(" - ")[0],
                        "url": topic.get("FirstURL", ""),
                        "content": topic.get("Text", ""),
                    }
                )
            elif isinstance(topic, dict) and "Topics" in topic:
                for sub in topic.get("Topics", []):
                    if len(results) >= max_results:
                        break
                    if isinstance(sub, dict) and "Text" in sub:
                        results.append(
                            {
                                "title": sub.get("Text", "").split(" - ")[0],
                                "url": sub.get("FirstURL", ""),
                                "content": sub.get("Text", ""),
                            }
                        )
    except Exception:
        pass

    # 2) Wikipedia 搜索兜底
    if len(results) < max_results:
        for lang in ("zh", "en"):
            try:
                remaining = max_results - len(results)
                if remaining <= 0:
                    break
                r = httpx.get(
                    f"https://{lang}.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "format": "json",
                        "srlimit": remaining,
                        "utf8": 1,
                    },
                    timeout=12.0,
                )
                r.raise_for_status()
                payload = r.json()
                for item in payload.get("query", {}).get("search", []):
                    title = item.get("title", "")
                    if not title:
                        continue
                    results.append(
                        {
                            "title": title,
                            "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
                            "content": _strip_html(item.get("snippet", "")),
                        }
                    )
                    if len(results) >= max_results:
                        break
            except Exception:
                continue

    return results[:max_results]


@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs, then fetches and returns full webpage content as markdown.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 1)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')

    Returns:
        Formatted search results with full webpage content
    """
    return run_research_search(query, max_results=max_results, topic=topic)


def run_research_search(
    query: str,
    max_results: int = 3,
    topic: Literal["general", "news", "finance"] = "general",
) -> str:
    """供研究智能体内部直接调用的搜索函数（非 Tool 形态）。"""
    result_texts = []

    # 1) 优先尝试 Tavily
    search_results = None
    client = _get_tavily_client()
    if client:
        try:
            search_results = client.search(
                query,
                max_results=max_results,
                topic=topic,
            )
        except Exception as e:
            result_texts.append(
                f"⚠ Tavily 不可用，已自动切换兜底搜索。原因: {str(e)}"
            )

    # 2) 使用 Tavily 结果
    if search_results and search_results.get("results"):
        for result in search_results.get("results", []):
            url = result.get("url", "")
            title = result.get("title", "Untitled")
            content = fetch_webpage_content(url) if url else result.get("content", "")
            result_text = f"""## {title}
**URL:** {url}

{content}

---
"""
            result_texts.append(result_text)
    else:
        # 3) 兜底搜索
        fallback_results = _fallback_web_search(query, max_results=max_results)
        if not fallback_results:
            return f"未检索到“{query}”的可用结果。"
        for item in fallback_results:
            result_text = f"""## {item.get("title", "Untitled")}
**URL:** {item.get("url", "")}

{item.get("content", "")}

---
"""
            result_texts.append(result_text)

    return f"""🔍 Found {len(result_texts)} result(s) for '{query}':

{chr(10).join(result_texts)}"""


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """用于对研究进展和决策进行战略反思的工具。

    请在每次搜索后使用此工具来分析结果并系统地规划下一步。
    这会在研究工作流中创造一个有意识的停顿，以确保做出高质量的决策。

    使用时机：
    - 收到搜索结果后：我发现了哪些关键信息？
    - 在决定下一步之前：我是否有足够的信息来全面回答？
    - 在评估研究空白时：我具体还缺少哪些信息？
    - 在结束研究之前：我现在能提供一个完整的答案吗？

    反思应涵盖以下内容：
    1. 分析当前发现 —— 我收集到了哪些具体信息？
    2. 差距评估 —— 还缺少哪些关键信息？
    3. 质量评估 —— 我是否有足够的证据/示例来给出一个好的答案？
    4. 战略决策 —— 我应该继续搜索还是直接提供答案？

    Args:
        reflection: 你对研究进展、发现、空白及下一步的详细反思

    Returns:
        确认反思已记录以辅助决策
    """
    return f"反思被记录: {reflection}"
