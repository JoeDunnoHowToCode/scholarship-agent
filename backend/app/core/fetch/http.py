"""httpx 轉接頭（ADR-027、ADR-028）：robots.txt、限速、條件式請求、被擋偵測。"""

import ssl
import time
from urllib.parse import urlsplit

import httpx
from protego import Protego

from app.core.fetch.base import BlockedError, FetchResult, TemporaryFetchError
from app.core.fetch.etiquette import detect_block, robots_allows


def tls_context() -> ssl.SSLContext:
    """憑證驗證照做（信任鏈、網域名稱、有效期限），只關掉 Python 3.13 預設的嚴格格式檢查。

    教育部憑證鏈的根憑證 TWCA Global Root CA 少了 Subject Key Identifier 欄位，
    嚴格檢查會拒絕連線（ADR-030）。
    """
    context = httpx.create_ssl_context()
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


class HttpFetcher:
    """符合 Fetcher 插座；用 httpx 的預設 User-Agent，不偽裝成瀏覽器（ADR-028）。"""

    def __init__(self, min_interval_seconds: float) -> None:
        self._client = httpx.Client(follow_redirects=True, timeout=30, verify=tls_context())
        self._min_interval = min_interval_seconds
        # 同一次執行內快取每個網站的 robots.txt（RFC 9309 允許快取最多 24 小時）
        self._robots: dict[str, tuple[int, str]] = {}
        # 每個網站上次請求的時間，用來限速
        self._last_request: dict[str, float] = {}

    @property
    def user_agent(self) -> str:
        return self._client.headers["user-agent"]

    def get(
        self, url: str, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        robots_status, robots_txt = self._robots_for(url)
        if not robots_allows(robots_status, robots_txt, url, self.user_agent):
            if robots_status >= 500:
                # 照 RFC 9309 這次不能抓；但這是對方伺服器暫時出錯，不是被擋，稍後再試（ADR-056）
                raise TemporaryFetchError(f"robots.txt 暫時無法讀取（{robots_status}）")
            raise BlockedError("robots.txt 禁止")

        # 條件式請求：把上次的 ETag／Last-Modified 帶給伺服器，沒更新它會回 304
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        response = self._request(url, robots_txt, headers)

        # httpx 會把 304 當成錯誤，所以先處理：沒更新就不用下載內容
        if response.status_code == 304:
            return FetchResult(str(response.url), 304, b"", "", etag, last_modified)
        content_type = response.headers.get("content-type", "")
        body = response.text if "html" in content_type else ""
        reason = detect_block(response.status_code, body)
        if reason:
            raise BlockedError(reason)  # 界線三：被擋就停，不換手法
        response.raise_for_status()  # 其他 4xx、5xx 交給呼叫端當成錯誤處理
        return FetchResult(
            url=str(response.url),
            status=response.status_code,
            content=response.content,
            content_type=content_type,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )

    def close(self) -> None:
        self._client.close()

    def _robots_for(self, url: str) -> tuple[int, str]:
        parts = urlsplit(url)
        if parts.netloc not in self._robots:
            robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
            response = self._request(robots_url, "", {})
            self._robots[parts.netloc] = (response.status_code, response.text)
        return self._robots[parts.netloc]

    def _request(
        self, url: str, robots_txt: str, headers: dict[str, str]
    ) -> httpx.Response:
        # 界線二：同一個網站兩次請求至少間隔 max(設定秒數, robots.txt 的 Crawl-delay)
        host = urlsplit(url).netloc
        interval = max(self._min_interval, self._crawl_delay(robots_txt))
        last = self._last_request.get(host)
        if last is not None:
            wait = last + interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        try:
            return self._client.get(url, headers=headers)
        finally:
            self._last_request[host] = time.monotonic()

    def _crawl_delay(self, robots_txt: str) -> float:
        if not robots_txt:
            return 0.0
        delay = Protego.parse(robots_txt).crawl_delay(self.user_agent)
        return float(delay) if delay else 0.0
