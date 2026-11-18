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


class Fine:
    """假的抓取器：網站恢復了，每一頁都回 304（沒變），不必寫快照檔。"""

    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        return FetchResult(url, 304, b"", "text/html", etag, last_modified)


def test_a_successful_retry_clears_the_block() -> None:
    from app.features.sources.models import Snapshot

    session = SessionLocal()
    try:
        today = datetime.now(TAIPEI).date()
        source = Source(name="Test recovered", url="https://test-recovered.example/", kind=SourceKind.UNIVERSITY,
                        manual_reason="429", retry_on=today)
        session.add(source)
        session.flush()
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=datetime.now(TAIPEI),
                             seen_at=datetime.now(TAIPEI), content_hash="8" * 64, file_path=f"{source.id}/test.html",
                             http_status=200, etag=None, last_modified=None))
        session.flush()
        fetch_source(session, Fine(), source)  # type: ignore[arg-type]
        assert (source.manual_reason, source.retry_on) == (None, None)  # 回到每天檢查
    finally:
        session.rollback()
        session.close()


def test_the_report_lists_only_sources_blocked_in_this_run() -> None:
    from app.features.sources.fetch import blocked_since

    session = SessionLocal()
    try:
        started = datetime.now(TAIPEI) - timedelta(hours=2)
        today = datetime.now(TAIPEI).date()
        now_blocked = Source(name="Test blocked today", url="https://test-blocked-today.example/",
                             kind=SourceKind.UNIVERSITY, manual_reason="429", retry_on=today + timedelta(days=7),
                             last_checked_at=started + timedelta(hours=1))
        old_block = Source(name="Test blocked last month", url="https://test-blocked-old.example/",
                           kind=SourceKind.UNIVERSITY, manual_reason="captcha", retry_on=None,
                           last_checked_at=started - timedelta(days=30))
        session.add_all([now_blocked, old_block])
        session.flush()
        listed = blocked_since(session, started)
        assert ("Test blocked today", "429", today + timedelta(days=7)) in listed
        assert all(name != "Test blocked last month" for name, _, _ in listed)
    finally:
        session.rollback()
        session.close()
