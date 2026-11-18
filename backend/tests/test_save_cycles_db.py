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


def test_a_date_without_a_year_becomes_the_next_such_day_marked_year_inferred() -> None:
    # B3 B（ADR-110）：原文只寫月日，AI 不填年份（驗證狀態 incomplete）；程式取今天以後最近的那一天，
    # 標 year_inferred；它不是預估（estimated 照舊是 False），所以照常送提醒
    from datetime import UTC, datetime

    session = SessionLocal()
    try:
        row = Scholarship(name="Test inferred year", countries=["FR"], degrees=["master"], nationality_scope="all",
                          nationalities=[], extracted={})
        session.add(row)
        session.flush()
        no_year = window(1, "scholarship").model_copy(update={"closes_year": None, "evidence": "1 March"})
        no_day = window(1, "scholarship").model_copy(update={"closes_year": None, "closes_day": None})
        save_cycles(session, row, [no_year, no_day], ["incomplete", "incomplete"])
        today = datetime.now(UTC).date()
        expected_year = today.year if (3, 1) >= (today.month, today.day) else today.year + 1
        built = session.scalars(select(Cycle).where(Cycle.scholarship_id == row.id)).all()
        assert [(c.closes_at.year, c.closes_at.month, c.closes_at.day) for c in built] == [(expected_year, 3, 1)]
        assert (built[0].verification, built[0].estimated) == ("year_inferred", False)  # 沒有日的照舊不建
    finally:
        session.rollback()
        session.close()


def test_a_year_the_ai_added_to_a_quote_without_a_year_is_replaced_by_the_inferred_year() -> None:
    # 總檢查 C1 第 4 種：WOCC 原文「Candidatez du 16/11 au 21/03」沒寫年份，AI 卻填了 2027；
    # 核對發現年份不在引用裡（year_not_in_quote），以前整筆丟掉、沒有申請期。改成丟掉 AI 的年份，由程式推算（ADR-110）
    from datetime import UTC, datetime

    session = SessionLocal()
    try:
        row = Scholarship(name="Test AI year", countries=["FR"], degrees=["master"], nationality_scope="all",
                          nationalities=[], extracted={})
        session.add(row)
        session.flush()
        ai_year = window(21, "scholarship").model_copy(
            update={"closes_year": 2031, "evidence": "Candidatez du 16/11 au 21/03"}
        )
        # 引用裡寫的是另一個年份：這是真的不一致，照舊不建（不能拿推算蓋掉原文寫的年份）
        other_year = window(9, "scholarship").model_copy(update={"closes_year": 2031, "evidence": "9 March 2026"})
        save_cycles(session, row, [ai_year, other_year], ["year_not_in_quote", "year_not_in_quote"])
        today = datetime.now(UTC).date()
        expected_year = today.year if (3, 21) >= (today.month, today.day) else today.year + 1
        built = session.scalars(select(Cycle).where(Cycle.scholarship_id == row.id)).all()
        assert [(c.closes_at.year, c.closes_at.month, c.closes_at.day) for c in built] == [(expected_year, 3, 21)]
        assert built[0].verification == "year_inferred"
    finally:
        session.rollback()
        session.close()
