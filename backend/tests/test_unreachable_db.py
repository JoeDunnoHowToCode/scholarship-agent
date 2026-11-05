"""天天抓不到的來源（ADR-080）在真的資料庫上跑：收尾時更新失敗天數、寫通知，標記後每 7 天才排一次。

用開發用的資料庫，在交易裡跑完就復原，不留任何資料（和 test_generate_db 一樣，11-04 的教訓：串接的程式也要真的跑一次）。
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.features.notifications.models import Event
from app.features.pipeline.jobs import due_source_ids, taipei_date, track_unreachable
from app.features.sources.models import Source
from app.shared.db import SessionLocal


def test_three_failed_days_on_the_real_database() -> None:
    session = SessionLocal()
    try:
        source = session.scalars(select(Source).where(Source.manual_reason.is_(None)).limit(1)).one()
        source.fail_days, source.last_failed_on, source.unreachable_since = 0, None, None
        start = datetime(2026, 11, 6, 2, 0, tzinfo=UTC)
        for day in range(3):
            track_unreachable(session, [(source.id, True, "ConnectTimeout: timed out")], start + timedelta(days=day))
        session.flush()
        third = taipei_date(start + timedelta(days=2))
        assert (source.fail_days, source.unreachable_since) == (3, third)
        added = [e for e in session.new if isinstance(e, Event)] + list(
            session.scalars(select(Event).where(Event.dedup_key == f"unreachable:{source.id}:{third}"))
        )
        assert any(e.dedup_key == f"unreachable:{source.id}:{third}" for e in added)
        # 標記後：隔天不排，最後一次失敗的 7 天後才排
        assert source.id not in due_source_ids(session, third + timedelta(days=1))
        assert source.id in due_source_ids(session, third + timedelta(days=7))
    finally:
        session.rollback()
        session.close()
