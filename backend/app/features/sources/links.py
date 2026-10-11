"""學程首頁的候選連結（ADR-031 第 3 層：列出同站連結，之後交給 AI 挑申請與獎學金頁）。"""

from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup

# 這些副檔名是檔案、不是網頁（交給 AI 挑也讀不到內容）
FILE_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".mp4",
)


@dataclass(frozen=True)
class Link:
    """頁面上的一個連結：完整網址與連結文字。"""

    url: str
    text: str


def candidate_links(html: str, page_url: str) -> list[Link]:
    """列出同一個網站的連結（相對網址轉成完整網址），保留出現順序。"""
    site = _site(page_url)
    # 本頁網址：去掉錨點和結尾的 /，用來排除連回自己的連結
    page = urldefrag(page_url).url.rstrip("/")
    found: list[Link] = []
    seen: set[str] = set()
    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        # 去掉 # 後面的錨點：它只在瀏覽器裡跳位置，伺服器收到的是同一頁
        url = urldefrag(urljoin(page_url, str(anchor["href"]))).url
        parts = urlsplit(url)
        # mailto:、javascript: 這類不是網頁；檔案看路徑副檔名（不看 ? 後面的參數）
        if parts.scheme not in ("http", "https") or parts.path.lower().endswith(FILE_EXTENSIONS):
            continue
        if _site(url) != site or url.rstrip("/") == page or url in seen:
            continue
        seen.add(url)
        # split + join 把換行和連續空白收成一格；只有圖示的連結改用 aria-label 或 title
        text = " ".join(anchor.get_text().split())
        text = text or str(anchor.get("aria-label") or anchor.get("title") or "")
        found.append(Link(url=url, text=text))
    return found


def _site(url: str) -> str | None:
    """網站名稱：主機名轉小寫、去掉開頭的 www.，讓 www.example.eu 和 example.eu 算同站。"""
    host = urlsplit(url).hostname  # hostname 已經是小寫
    return host.removeprefix("www.") if host else None
