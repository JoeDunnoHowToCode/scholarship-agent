"""段 9（ADR-119）：詳細頁與列表卡片拿到「申請方式」與「沒有申請期的原因」那一句話。真的資料庫，交易裡跑完就復原。"""

from datetime import UTC, date, datetime

from app.features.scholarships.api import read_scholarship, to_row
from app.features.scholarships.models import Scholarship
from app.shared.db import SessionLocal


def test_detail_and_card_say_how_to_apply_and_why_there_is_no_date() -> None:
    session = SessionLocal()
    try:
        row = Scholarship(
            name="Test labels", countries=["FI"], degrees=["master"], nationality_scope="excluded",
            nationalities=["FR"], how_to_apply="with_admission", no_date_reason="admission_date_elsewhere",
            extracted={"how_to_apply": "with_admission", "how_to_apply_evidence": "All applicants are considered.",
                       "verification": {"how_to_apply": "supported"}, "nationality_groups": ["EU", "EEA"]},
        )
        session.add(row)
        session.flush()
        sentence = "跟著入學申請一起審，截止日就是入學申請的截止日；官網這幾頁沒寫，請看學校的入學申請頁"
        detail = read_scholarship(row.id, session)
        assert (detail.how_to_apply, detail.how_to_apply_evidence) == ("with_admission", "All applicants are considered.")
        assert detail.no_date_text == sentence
        assert detail.nationality_groups == ["歐盟", "歐洲經濟區"]  # 「除了歐盟、歐洲經濟區」，不用自己數 30 國
        card = to_row(row, None, date(2026, 11, 21), None, datetime(2026, 11, 21, tzinfo=UTC))
        assert card.no_date_text == sentence
    finally:
        session.rollback()
        session.close()


def test_an_unreachable_site_says_the_day_it_was_last_reached() -> None:
    # 段 9：「資料停在哪天」是最後一次抓到官網的日子（快照），不是重抽的日子（last_verified_at）
    from app.features.sources.models import Snapshot, Source, SourceKind

    session = SessionLocal()
    try:
        source = Source(name="Test unreachable", url="https://test-unreachable.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        seen = datetime(2026, 10, 11, 3, 0, tzinfo=UTC)
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=seen, seen_at=seen, content_hash="c" * 64,
                             file_path="/nonexistent", http_status=200, etag=None, last_modified=None))
        row = Scholarship(name="Test unreachable", countries=["FI"], degrees=["master"], nationality_scope="all",
                          nationalities=[], source_id=source.id, no_date_reason="unreachable", extracted={},
                          last_verified_at=datetime(2026, 11, 20, tzinfo=UTC))
        session.add(row)
        session.flush()
        assert read_scholarship(row.id, session).no_date_text == "官網最近抓不到，資料停在 2026-10-11，請直接看官網"
    finally:
        session.rollback()
        session.close()
