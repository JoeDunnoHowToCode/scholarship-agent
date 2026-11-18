"""每天的 refresh 依來源狀態封存獎學金（總檢查 A6）：被排除、停用的來源，獎學金不該留在列表上。

真的資料庫，交易裡跑完就復原。
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.features.scholarships.cycles import refresh
from app.features.scholarships.models import Cycle, Scholarship, ScholarshipStatus
from app.features.sources.models import Source, SourceKind, SourceStatus
from app.shared.db import SessionLocal

NOW = datetime.now(UTC)


def scholarship_with_open_cycle(session: Session, status: SourceStatus, enabled: bool) -> tuple[Source, Scholarship]:
    """一個來源＋一筆獎學金，申請期 60 天後截止（即將開放），所以照申請期的規則不會被封存。"""
    source = Source(
        name="Test refresh source", url=f"https://test-refresh-{status.value}-{enabled}.example/",
        kind=SourceKind.UNIVERSITY, status=status, enabled=enabled,
    )
    session.add(source)
    session.flush()
    row = Scholarship(name="Test refresh scholarship", source_id=source.id, extracted={})
    session.add(row)
    session.flush()
    session.add(Cycle(scholarship_id=row.id, closes_at=NOW + timedelta(days=60), status="upcoming"))
    session.flush()
    session.refresh(row)
    return source, row


def test_refresh_archives_scholarships_of_a_rejected_source() -> None:
    # A6：#309 的來源因為「國籍規定排除台灣」被排除，獎學金卻還是使用中、出現在列表上
    session = SessionLocal()
    try:
        _, row = scholarship_with_open_cycle(session, SourceStatus.REJECTED, enabled=False)
        refresh(session, NOW)
        assert row.status == ScholarshipStatus.ARCHIVED
    finally:
        session.rollback()
        session.close()


def test_refresh_archives_a_scholarship_that_the_page_says_is_not_offered() -> None:
    # 總檢查 C3（ADR-114）：TISE Master 原文寫明這一屆沒有獎學金（offered = no），程式不建申請期；
    # 以前「一個申請期都沒有就不封存」，所以 27 筆今年申請不到的一直留在列表上
    session = SessionLocal()
    try:
        source = Source(name="Test not offered", url="https://test-refresh-not-offered.example/",
                        kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        row = Scholarship(name="Test not offered", source_id=source.id, extracted={"offered": "no"})
        session.add(row)
        session.flush()
        refresh(session, NOW)
        assert row.status == ScholarshipStatus.ARCHIVED
    finally:
        session.rollback()
        session.close()
