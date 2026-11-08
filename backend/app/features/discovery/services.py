"""工具背後實際連網的做法：Tavily 搜尋（ADR-085）、用現有的抓取程式讀網頁（ADR-027、028）。"""

from datetime import datetime

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.fetch.base import Fetcher
from app.core.fetch.text import decode_snapshot, html_to_text, pdf_to_text
from app.features.costs.usage import month_start
from app.features.discovery.models import AgentStep
from app.features.discovery.tools import Page, SearchHit, SearchUnavailable, page_links

TAVILY_URL = "https://api.tavily.com/search"
RESULTS_PER_SEARCH = 5


def tavily_search(client: httpx.Client, api_key: SecretStr, query: str) -> list[SearchHit]:
    """Tavily 基本搜尋（一次 1 點）。額度用完或金鑰無效時丟 SearchUnavailable。"""
    response = client.post(
        TAVILY_URL,
        headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
        json={"query": query, "search_depth": "basic", "max_results": RESULTS_PER_SEARCH},
        timeout=30,
    )
    # 錯誤訊息只寫狀態碼，不帶請求內容：請求標頭裡有金鑰（第 8 天的教訓）
    if response.status_code == 401:
        raise SearchUnavailable("Tavily 金鑰無效或沒設定（401）")
    if response.status_code in (432, 433):
        raise SearchUnavailable(f"Tavily 額度用完（{response.status_code}）")
    if response.status_code >= 400:
        raise SearchUnavailable(f"Tavily 回應錯誤（{response.status_code}）")
    return [
        SearchHit(str(item.get("title", "")), str(item["url"]), str(item.get("content", "")))
        for item in response.json().get("results", [])
    ]


def fetch_page(fetcher: Fetcher, url: str) -> Page:
    """抓一頁（遵守 robots.txt、每站限速、被擋就丟 BlockedError），轉成可見文字與連結。"""
    result = fetcher.get(url)
    if "pdf" in result.content_type or result.content[:4] == b"%PDF":
        return Page(result.url, pdf_to_text(result.content), [])
    html = decode_snapshot(result.content)
    return Page(result.url, html_to_text(html), page_links(html, result.url))


def searches_this_month(session: Session, now: datetime) -> int:
    """本月（台灣時間的月份）agent 已經搜尋幾次，從 agent_steps 算。"""
    count = session.scalar(
        select(func.count()).select_from(AgentStep).where(
            AgentStep.kind == "tool", AgentStep.tool == "search", AgentStep.created_at >= month_start(now)
        )
    )
    return int(count or 0)
