"""找出重複的獎學金（ADR-048）：只用規則比對網址、提供者和名稱，不花 AI 費用。"""

import unicodedata
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    """把寫法不同、其實同一頁的網址變成同一個字串。

    例如 "HTTP://www.Example.eu/Apply/#deadlines" → "https://example.eu/Apply"。
    路徑的大小寫和查詢字串（? 後面）保留，因為它們可能指向不同的頁面。
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme == "http":
        scheme = "https"  # 同一個網站通常 http 會轉到 https
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")  # 結尾的 / 有沒有都是同一頁
    return urlunsplit((scheme, host, path, parts.query, ""))  # 最後的空字串：丟掉 # 錨點


def normalize_name(text: str) -> str:
    """名稱只留文字和數字，方便比對。

    全形轉半形（NFKC）、不分大小寫（casefold），再去掉空白、標點和符號（例如「–」）。
    中文字也算文字，會保留。
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(char for char in text if char.isalnum())
