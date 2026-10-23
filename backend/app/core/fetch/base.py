"""抓取插座（ADR-005）：功能程式只依賴這個介面；之後的瀏覽器轉接頭也實作它。"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FetchResult:
    url: str  # 跟隨轉址後的網址
    status: int  # 200 或 304
    content: bytes  # 304 時是空的
    content_type: str
    etag: str | None
    last_modified: str | None


class BlockedError(Exception):
    """網站不讓我們抓（ADR-028）：原因寫在 reason，例如「403」「robots.txt 禁止」。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TemporaryFetchError(Exception):
    """網站暫時讀不到（例如 robots.txt 回 5xx）：這次不能抓，但不是被擋，稍後再試（ADR-056）。"""


class Fetcher(Protocol):
    def get(
        self, url: str, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult: ...
