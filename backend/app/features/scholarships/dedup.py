"""找出重複的獎學金（ADR-048）：只用規則比對網址、提供者和名稱，不花 AI 費用。"""

import unicodedata
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Candidate:
    """要比對的一筆獎學金：只放比對需要的欄位。"""

    id: int
    provider: str | None
    name: str
    official_url: str | None


def find_duplicates(items: list[Candidate]) -> dict[int, int]:
    """回傳 {重複的 id: 代表的 id}；沒有重複的不會出現。

    兩筆算重複：官方網址相同，或「提供者＋名稱」都相同。
    只比名稱不夠：很多不同學程都叫 "Erasmus Mundus Scholarships"。
    重複會傳遞（A 像 B、B 像 C，三筆就是同一組），每組由最小的 id 代表。
    """
    # 併查集（union-find）：每筆記住自己的「上一層」，一路往上找到的就是組長
    parent = {item.id: item.id for item in items}

    def leader(item_id: int) -> int:
        while parent[item_id] != item_id:
            item_id = parent[item_id]
        return item_id

    first_with_key: dict[tuple[str, ...], int] = {}  # 比對鍵 → 第一個有這個鍵的 id
    for item in items:
        keys: list[tuple[str, ...]] = []
        if item.official_url:
            keys.append(("url", normalize_url(item.official_url)))
        if item.provider:
            keys.append(("provider+name", normalize_name(item.provider), normalize_name(item.name)))
        for key in keys:
            if key not in first_with_key:
                first_with_key[key] = item.id
                continue
            # 合併兩組：id 較大的組長改掛到較小的組長底下
            a, b = leader(first_with_key[key]), leader(item.id)
            parent[max(a, b)] = min(a, b)
    return {item.id: leader(item.id) for item in items if leader(item.id) != item.id}
