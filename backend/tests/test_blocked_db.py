"""被擋的來源記下再試日期、到期再試、成功就恢復（ADR-116）。真的資料庫，交易裡跑完就復原。"""

from datetime import datetime, timedelta

from app.core.fetch.base import BlockedError, FetchResult
from app.features.costs.usage import TAIPEI
from app.features.sources.fetch import fetch_source
from app.features.sources.models import Source, SourceKind
from app.shared.db import SessionLocal


class Blocked:
    """假的抓取器：每一頁都說被擋了。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        raise BlockedError(self.reason)


def test_a_429_marks_the_source_with_a_retry_date() -> None:
    session = SessionLocal()
    try:
        source = Source(name="Test busy site", url="https://test-busy.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        fetch_source(session, Blocked("429"), source)  # type: ignore[arg-type]
        today = datetime.now(TAIPEI).date()
        assert (source.manual_reason, source.retry_on) == ("429", today + timedelta(days=7))
    finally:
        session.rollback()
        session.close()
