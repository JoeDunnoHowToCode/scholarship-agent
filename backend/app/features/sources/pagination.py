"""翻頁連結（ADR-029：EACEA 目錄含翻頁）。"""

from urllib.parse import parse_qs, urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup


def pagination_urls(html: str, page_url: str, *, page_zero_is_first: bool = False) -> list[str]:
    """找出同一路徑的 ?page=數字 連結，轉成完整網址、去掉重複（保留出現順序）。"""
    base = urlsplit(page_url)
    found: list[str] = []
    for link in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        # 去掉 # 後面的錨點：它只在瀏覽器裡跳位置，伺服器收到的是同一頁
        url = urldefrag(urljoin(page_url, str(link["href"]))).url
        parts = urlsplit(url)
        page = parse_qs(parts.query).get("page", [""])[0]
        same_path = (parts.netloc, parts.path) == (base.netloc, base.path)
        if same_path and page.isdigit() and url not in found:
            found.append(url)
    return found
