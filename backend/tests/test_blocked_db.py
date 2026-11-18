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


def test_a_blocked_source_is_checked_again_on_its_retry_date_and_not_before() -> None:
    from app.features.pipeline.jobs import due_source_ids

    session = SessionLocal()
    try:
        today = datetime.now(TAIPEI).date()
        due = Source(name="Test retry today", url="https://test-retry-today.example/", kind=SourceKind.UNIVERSITY,
                     manual_reason="429", retry_on=today)
        later = Source(name="Test retry later", url="https://test-retry-later.example/", kind=SourceKind.UNIVERSITY,
                       manual_reason="403", retry_on=today + timedelta(days=3))
        manual = Source(name="Test captcha", url="https://test-captcha.example/", kind=SourceKind.UNIVERSITY,
                        manual_reason="captcha", retry_on=None)
        session.add_all([due, later, manual])
        session.flush()
        ids = due_source_ids(session, today)
        assert (due.id in ids, later.id in ids, manual.id in ids) == (True, False, False)
    finally:
        session.rollback()
        session.close()
