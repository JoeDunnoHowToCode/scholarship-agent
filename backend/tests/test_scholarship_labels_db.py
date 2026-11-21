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
