"""舊網址、消失的子頁（11-09 使用者選 C）：記下每個網址最後一次還抓得到的時間，
抽取只用最近還在的；子頁或舊網址連不上不讓整個來源失敗；很久都抓不到的不再去抓。真的資料庫，交易裡跑完就復原。"""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.fetch.base import FetchResult
from app.features.scholarships.extract import documents
from app.features.sources.fetch import fetch_source
from app.features.sources.models import Snapshot, Source, SourceKind
from app.shared.db import SessionLocal

NOW = datetime.now(UTC)
HOME = "https://test-seen.example/"
OLD = "https://test-seen-old-domain.example/apply"  # 換網址前的舊網站
RETIRED = "https://test-seen.example/gone-long-ago"


class Fetcher:
    """首頁回 304（沒變）；舊網址連不上；記下抓了哪些網址。"""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        self.asked.append(url)
        if url == OLD:
            raise httpx.ConnectError("nodename nor servname provided", request=httpx.Request("GET", url))
        return FetchResult(url, 304, b"", "text/html", etag, last_modified)


def snapshot(session: Session, source: Source, url: str, seen: datetime) -> Snapshot:
    row = Snapshot(source_id=source.id, url=url, fetched_at=seen, seen_at=seen, content_hash=url[-12:].rjust(64, "0"),
                   file_path=f"{source.id}/test.html", http_status=200, etag=None, last_modified=None)
    session.add(row)
    return row


def test_old_urls_do_not_fail_the_source_and_drop_out_of_extraction() -> None:
    session = SessionLocal()
    try:
        source = Source(name="Test seen", url=HOME, kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        home = snapshot(session, source, HOME, NOW - timedelta(days=20))
        old = snapshot(session, source, OLD, NOW - timedelta(days=20))
        snapshot(session, source, RETIRED, NOW - timedelta(days=40))
        session.flush()
        fetcher = Fetcher()
        try:
            fetch_source(session, fetcher, source)  # type: ignore[arg-type]
            failed: Exception | None = None
        except httpx.HTTPError as error:
            failed = error
        assert failed is None, f"舊網址連不上不該讓整個來源失敗：{failed}"
        assert RETIRED not in fetcher.asked  # 超過 30 天都抓不到的網址不再去抓
        assert home.seen_at is not None and home.seen_at > NOW - timedelta(minutes=5)  # 304 也算抓得到
        assert old.seen_at == NOW - timedelta(days=20)  # 連不上：時間不更新
        # 抽取只用最近一輪還抓得到的網址（容許 7 天）
        assert [s.url for s in documents(session, source)] == [HOME]
    finally:
        session.rollback()
        session.close()
