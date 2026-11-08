"""agent 的三種工具（ADR-084）：搜尋、讀網頁、提交。沒有改資料庫或讀個人資料的工具。

搜尋與讀網頁的實際做法用參數傳進來（searcher、reader），測試時換成假的，不連網。
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.features.discovery.agent import Tool
from app.features.sources.links import Link

SEARCHES_PER_MONTH = 800  # Tavily 免費每月 1,000 次，留 200 次餘裕（「Claude 自行決定」第 6 點）
PAGE_CHARS = 20_000  # 讀網頁時給 AI 的文字上限（第 7 點）
PAGE_LINKS = 150  # 讀網頁時列出的連結上限（第 7 點）


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    content: str  # 搜尋服務給的摘要


@dataclass(frozen=True)
class Page:
    url: str  # 跟隨轉址後的網址
    text: str  # 可見文字
    links: list[Link]


class SearchUnavailable(Exception):
    """搜尋服務不能用了（額度用完、金鑰無效）：這次執行就停。"""


@dataclass(frozen=True)
class Submission:
    url: str
    reason: str


@dataclass
class Toolbox:
    searcher: Callable[[str], list[SearchHit]]
    reader: Callable[[str], Page]
    searches_left: int  # 本月還能搜尋幾次
    start_urls: list[str] = field(default_factory=list)  # 任務一開始就給的網址（例如學校首頁），可以直接讀
    max_submissions: int = 3
    seen: set[str] = field(default_factory=set)  # 這次執行看過的網址：搜尋結果、讀過的頁面和上面的連結
    submissions: list[Submission] = field(default_factory=list)

    def tools(self, with_search: bool = True) -> list[Tool]:
        return []  # 骨架


def page_links(html: str, page_url: str) -> list[Link]:
    """頁面上所有網頁連結（含別的網站），去掉檔案、mailto 這類。"""
    return []  # 骨架
