"""工具背後實際連網的做法：Tavily 搜尋（ADR-085）、用現有的抓取程式讀網頁（ADR-027、028）。"""

from datetime import datetime

import httpx
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.fetch.base import Fetcher
from app.features.discovery.tools import Page, SearchHit

TAVILY_URL = "https://api.tavily.com/search"
RESULTS_PER_SEARCH = 5


def tavily_search(client: httpx.Client, api_key: SecretStr, query: str) -> list[SearchHit]:
    """Tavily 基本搜尋（一次 1 點）。額度用完或金鑰無效時丟 SearchUnavailable。"""
    return []  # 骨架


def fetch_page(fetcher: Fetcher, url: str) -> Page:
    """抓一頁（遵守 robots.txt、每站限速、被擋就丟 BlockedError），轉成可見文字與連結。"""
    return Page(url, "", [])  # 骨架


def searches_this_month(session: Session, now: datetime) -> int:
    """本月（台灣時間的月份）agent 已經搜尋幾次，從 agent_steps 算。"""
    return 0  # 骨架
