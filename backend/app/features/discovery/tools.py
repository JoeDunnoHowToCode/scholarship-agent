"""agent 的三種工具（ADR-084）：搜尋、讀網頁、提交。沒有改資料庫或讀個人資料的工具。

搜尋與讀網頁的實際做法用參數傳進來（searcher、reader），測試時換成假的，不連網。
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup

from app.core import prompts
from app.core.llm.base import ToolSpec
from app.features.discovery.agent import StopAgent, Tool
from app.features.sources.links import FILE_EXTENSIONS, Link

# 工具說明也是提示詞（ADR-088）：AI 靠它決定什麼時候用哪個工具
SEARCH_VERSION = "tool-search-1"
READ_VERSION = "tool-read-page-1"
SUBMIT_VERSION = "tool-submit-1"

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

    def __post_init__(self) -> None:
        self.seen.update(self.start_urls)

    def tools(self, with_search: bool = True) -> list[Tool]:
        url = {"type": "string", "description": "完整網址"}
        found = [
            Tool(ToolSpec("read_page", prompts.load(READ_VERSION),
                          {"type": "object", "properties": {"url": url}, "required": ["url"]}), self._read),
            Tool(ToolSpec("submit", prompts.load(SUBMIT_VERSION), {
                "type": "object",
                "properties": {"url": url, "reason": {"type": "string", "description": "一句話說明為什麼是碩士獎學金頁"}},
                "required": ["url", "reason"],
            }), self._submit),
        ]
        if with_search:
            query = {"type": "string", "description": "搜尋字"}
            found.insert(0, Tool(ToolSpec("search", prompts.load(SEARCH_VERSION),
                                          {"type": "object", "properties": {"query": query}, "required": ["query"]}),
                                 self._search))
        return found

    def _search(self, args: dict[str, Any]) -> str:
        if self.searches_left <= 0:
            raise StopAgent(f"本月搜尋次數已達上限（{SEARCHES_PER_MONTH} 次）")
        self.searches_left -= 1
        try:
            hits = self.searcher(str(args["query"]))
        except SearchUnavailable as error:
            raise StopAgent(str(error)) from error
        self.seen.update(hit.url for hit in hits)
        if not hits:
            return "沒有結果"
        return "\n".join(f"{n}. {hit.title}\n   {hit.url}\n   {hit.content[:300]}" for n, hit in enumerate(hits, 1))

    def _read(self, args: dict[str, Any]) -> str:
        url = str(args["url"])
        if url not in self.seen:
            return "這個網址這次沒看過，不能打開：只能讀任務給的網址、搜尋結果，或讀過的頁面上的連結"
        page = self.reader(url)
        self.seen.add(page.url)
        self.seen.update(link.url for link in page.links)
        text = page.text[:PAGE_CHARS] + ("\n（已截斷）" if len(page.text) > PAGE_CHARS else "")
        listing = "\n".join(f"- {link.text or '（無文字）'} | {link.url}" for link in page.links[:PAGE_LINKS])
        more = f"\n（還有 {len(page.links) - PAGE_LINKS} 個連結已截斷）" if len(page.links) > PAGE_LINKS else ""
        return f"網址：{page.url}\n\n{text}\n\n頁面上的連結（連結文字 | 網址）：\n{listing}{more}"

    def _submit(self, args: dict[str, Any]) -> str:
        url, reason = str(args["url"]), str(args.get("reason", ""))
        # 只收這次看過的網址：防止 AI 編造或改寫網址（和第 3 天挑連結的做法一樣）
        if url not in self.seen:
            return "這個網址這次沒看過，不能提交：只能提交搜尋結果或讀過的頁面上出現的網址"
        if any(s.url == url for s in self.submissions):
            return f"已經提交過了：{url}"
        if len(self.submissions) >= self.max_submissions:
            return f"這次執行的提交數已達上限（{self.max_submissions} 個），請結束"
        self.submissions.append(Submission(url, reason))
        return f"已提交：{url}"


def page_links(html: str, page_url: str) -> list[Link]:
    """頁面上所有網頁連結（含別的網站），去掉檔案、mailto 這類，保留出現順序。"""
    found: list[Link] = []
    seen: set[str] = set()
    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        url = urldefrag(urljoin(page_url, str(anchor["href"]))).url
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or parts.path.lower().endswith(FILE_EXTENSIONS) or url in seen:
            continue
        seen.add(url)
        text = " ".join(anchor.get_text().split()) or str(anchor.get("aria-label") or anchor.get("title") or "")
        found.append(Link(url=url, text=text))
    return found
