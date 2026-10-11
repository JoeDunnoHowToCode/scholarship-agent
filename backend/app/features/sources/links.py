"""學程首頁的候選連結（ADR-031 第 3 層：列出同站連結，之後交給 AI 挑申請與獎學金頁）。"""

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Link:
    """頁面上的一個連結：完整網址與連結文字。"""

    url: str
    text: str


def candidate_links(html: str, page_url: str) -> list[Link]:
    """列出同一個網站的連結（相對網址轉成完整網址），保留出現順序。"""
    site = _site(page_url)
    found: list[Link] = []
    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        url = urljoin(page_url, str(anchor["href"]))
        if _site(url) != site:
            continue
        # split + join 把換行和連續空白收成一格
        found.append(Link(url=url, text=" ".join(anchor.get_text().split())))
    return found


def _site(url: str) -> str | None:
    """網站名稱：主機名轉小寫、去掉開頭的 www.，讓 www.example.eu 和 example.eu 算同站。"""
    host = urlsplit(url).hostname  # hostname 已經是小寫
    return host.removeprefix("www.") if host else None
