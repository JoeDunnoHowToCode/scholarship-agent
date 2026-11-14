"""申請期只從「申請這個獎學金」的日期產生（ADR-105）。真的資料庫，交易裡跑完就復原。"""

from sqlalchemy import select

from app.features.scholarships.extract import save_cycles
from app.features.scholarships.models import Cycle, Scholarship
from app.features.scholarships.schemas import WindowDraft
from app.shared.db import SessionLocal


def window(day: int, kind: str) -> WindowDraft:
    return WindowDraft.model_validate({
        "label": None, "intake": "2027", "opens_year": None, "opens_month": None, "opens_day": None,
        "closes_year": 2027, "closes_month": 3, "closes_day": day, "closes_time": None, "timezone": "Europe/Paris",
        "nationality_scope": "all", "nationalities": [], "funding": "any", "evidence": f"{day} March 2027",
        "kind": kind,
    })


def test_only_scholarship_dates_become_cycles_and_not_when_it_is_not_offered() -> None:
    session = SessionLocal()
    try:
        row = Scholarship(name="Test kinds", countries=["FR"], degrees=["master"], nationality_scope="all",
                          nationalities=[], extracted={})
        session.add(row)
        session.flush()
        windows = [window(1, "scholarship"), window(9, "document"), window(16, "payment"), window(20, "admission_only")]
        save_cycles(session, row, windows, ["supported"] * 4)
        days = sorted(c.closes_at.day for c in session.scalars(select(Cycle).where(Cycle.scholarship_id == row.id)))
        assert days == [1]  # 補件、繳費、只有入學的日期不是申請期
        # 原文寫明這次不提供：一個申請期都不建
        save_cycles(session, row, windows, ["supported"] * 4, offered="no")
        assert session.scalars(select(Cycle).where(Cycle.scholarship_id == row.id)).all() == []
    finally:
        session.rollback()
        session.close()
