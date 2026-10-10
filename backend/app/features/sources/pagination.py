"""翻頁連結（ADR-029：EACEA 目錄含翻頁）。"""

from urllib.parse import (
    parse_qs,
    parse_qsl,
    urldefrag,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)

from bs4 import BeautifulSoup


def pagination_urls(html: str, page_url: str, *, page_zero_is_first: bool = False) -> list[str]:
    """找出同一路徑的 ?page=數字 連結，轉成完整網址、去掉重複（保留出現順序）。

    page_zero_is_first 打開時（目前只有 EACEA），?page=0 就是首頁本身，換成不帶頁碼的網址。
    """
    base = urlsplit(page_url)
    found: list[str] = []
    for link in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        # 去掉 # 後面的錨點：它只在瀏覽器裡跳位置，伺服器收到的是同一頁
        url = urldefrag(urljoin(page_url, str(link["href"]))).url
        parts = urlsplit(url)
        page = parse_qs(parts.query).get("page", [""])[0]
        same_path = (parts.netloc, parts.path) == (base.netloc, base.path)
        if not (same_path and page.isdigit()):
            continue
        if page_zero_is_first and page == "0":
            # 拿掉 page 參數，變回首頁網址（其他參數保留）
            query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if key != "page"])
            url = urlunsplit(parts._replace(query=query))
        if url not in found:
            found.append(url)
    return found


def missing_pages_warning(previous: int | None, current: int) -> str | None:
    if previous is not None:
        return f"只抓到 {current} 頁（上次 {previous} 頁），翻頁可能失效"
    return None
