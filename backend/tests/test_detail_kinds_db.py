"""詳細頁回傳 ADR-105 的新欄位：今年有沒有開、其他時程；同一頁其他補助的錢不顯示。真的資料庫，交易裡跑完就復原。"""

from app.features.scholarships import api
from app.features.scholarships.models import Scholarship
from app.shared.db import SessionLocal

WINDOW = {"label": "Document upload", "intake": None, "opens_year": None, "opens_month": None, "opens_day": None,
          "closes_year": 2027, "closes_month": 3, "closes_day": 16, "closes_time": None, "timezone": None,
          "nationality_scope": "all", "nationalities": [], "funding": "any",
          "evidence": "Upload documents by 16 March 2027", "kind": "document"}
AMOUNT = {"value": 1400, "currency": "EUR", "period": "month", "kind": "living_allowance", "applies_to": None,
          "evidence": "EUR 1,400 per month"}


def test_detail_shows_offered_and_other_dates_and_hides_other_awards() -> None:
    session = SessionLocal()
    try:
        row = Scholarship(
            name="Test detail kinds", countries=["FR"], degrees=["master"], nationality_scope="all", nationalities=[],
            extracted={
                "offered": "no", "offered_evidence": "No scholarships for the 2027 intake",
                "windows": [{**WINDOW, "kind": "scholarship", "label": None}, WINDOW],
                "amounts": [AMOUNT, {**AMOUNT, "value": 300, "for_this": False}],
                "verification": {"deadlines": ["supported", "supported"], "amounts": ["supported", "supported"]},
            },
        )
        session.add(row)
        session.flush()
        detail = api.read_scholarship(row.id, session)
        assert (detail.offered, detail.offered_evidence) == ("no", "No scholarships for the 2027 intake")
        assert [(d.kind, d.label, d.closes, d.evidence) for d in detail.other_dates] == [
            ("document", "Document upload", "2027-03-16", "Upload documents by 16 March 2027"),
        ]
        assert [a.value for a in detail.amounts] == [1400]
    finally:
        session.rollback()
        session.close()
