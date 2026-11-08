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
        # 通知不再一則一則寫（11-08 使用者選 C），改由下一個測試檢查交給每日報告
        # 標記後：隔天不排，最後一次失敗的 7 天後才排
        assert source.id not in due_source_ids(session, third + timedelta(days=1))
        assert source.id in due_source_ids(session, third + timedelta(days=7))
    finally:
        session.rollback()
        session.close()


def test_marked_and_recovered_sources_go_into_the_daily_report() -> None:
    # 11-08 使用者選 C：不再一則一則送，收尾時交給每日檢查報告
    session = SessionLocal()
    try:
        source = session.scalars(select(Source).where(Source.manual_reason.is_(None)).limit(1)).one()
        source.fail_days, source.last_failed_on, source.unreachable_since = 0, None, None
        start = datetime(2026, 11, 6, 2, 0, tzinfo=UTC)
        results = [
            track_unreachable(session, [(source.id, True, "gaierror: nodename nor servname provided")], start + timedelta(days=day))
            for day in range(3)
        ]
        session.flush()
        third = taipei_date(start + timedelta(days=2))
        assert results[0] == ([], []) and results[1] == ([], [])
        marked, recovered = results[2]
        assert [error for _, error in marked] == ["gaierror: nodename nor servname provided"] and recovered == []
        assert session.scalars(select(Event).where(Event.dedup_key == f"unreachable:{source.id}:{third}")).first() is None
        # 之後抓到了：交給報告的「抓得到了」
        later = start + timedelta(days=9)
        _, recovered = track_unreachable(session, [(source.id, False, "")], later)
        assert recovered == [marked[0][0]]
    finally:
        session.rollback()
        session.close()


def test_the_last_error_is_remembered_and_cleared_on_success() -> None:
    # 11-09 使用者選 B：要知道「為什麼抓不到」，才能決定要不要派 agent 找新官網
    session = SessionLocal()
    try:
        source = session.scalars(select(Source).where(Source.manual_reason.is_(None)).limit(1)).one()
        now = datetime(2026, 11, 9, 2, 0, tzinfo=UTC)
        track_unreachable(session, [(source.id, True, "gaierror: nodename nor servname provided")], now)
        assert source.last_error == "gaierror: nodename nor servname provided"
        track_unreachable(session, [(source.id, False, "")], now + timedelta(days=1))
        assert source.last_error is None
    finally:
        session.rollback()
        session.close()
