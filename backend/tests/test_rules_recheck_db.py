"""已存的抽取結果重新套用程式規則（ADR-103）：不呼叫 AI。真的資料庫，交易裡跑完就復原。"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.features.scholarships.extract import recheck_rules
from app.features.scholarships.models import Cycle, Scholarship
from app.features.sources.models import Snapshot, Source, SourceKind
from app.shared.db import SessionLocal

QUOTE = "A monthly allowance of EUR 1,400, in total EUR 33,600."
WINDOW_QUOTE = "Applications open 1 October 2026 and close 15 January 2007"


def amount(value: float, period: str) -> dict[str, object]:
    return {"value": value, "currency": "EUR", "period": period, "kind": "living_allowance", "applies_to": None,
            "evidence": QUOTE, "status": "supported"}


def test_saved_extractions_get_the_rules_without_calling_the_ai(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text(f"<html><body><p>{QUOTE}</p><p>{WINDOW_QUOTE}.</p></body></html>", encoding="utf-8")
    window = {"label": None, "intake": None, "opens_year": 2026, "opens_month": 10, "opens_day": 1,
              "closes_year": 2007, "closes_month": 1, "closes_day": 15, "closes_time": None, "timezone": None,
              "nationality_scope": "all", "nationalities": [], "funding": "any", "evidence": WINDOW_QUOTE}
    session = SessionLocal()
    try:
        source = Source(name="Test recheck", url="https://test-recheck.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        now = datetime.now(UTC)
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                             content_hash="c" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
        row = Scholarship(
            name="Test recheck", source_id=source.id, countries=["SE"], degrees=["master"],
            nationality_scope="all", nationalities=[],
            extracted={
                "amounts": [amount(1400, "month"), amount(1400, "month"), amount(33600, "total")],
                "windows": [window],
                "verification": {"nationality": "supported", "degrees": "supported", "deadlines": ["supported"],
                                 "amounts": ["supported"] * 3, "categories": {}, "issues": []},
                "meta": {"snapshots": ["c" * 64], "prompts": [], "model": "fake"},
            },
        )
        session.add(row)
        session.flush()

        checked, changed = recheck_rules(session, [source.id])

        assert (checked, changed) == (1, 1)
        session.refresh(row)
        assert [(a["value"], a["period"]) for a in row.extracted["amounts"]] == [(1400, "month")]
        assert row.extracted["verification"]["amounts"] == ["supported"]
        assert row.extracted["verification"]["deadlines"] == ["closes_before_opens"]
        assert row.amount is not None and "33,600" not in row.amount
        cycle = session.scalars(select(Cycle).where(Cycle.scholarship_id == row.id)).one()
        assert cycle.verification == "closes_before_opens"
    finally:
        session.rollback()
        session.close()


def test_rechecked_amounts_keep_the_extraction_format(tmp_path: Path) -> None:
    # 抽取存的金額沒有 status（核對結果在 verification.amounts），重新套用規則後格式要一樣
    page = tmp_path / "page.html"
    page.write_text(f"<html><body><p>{QUOTE}</p></body></html>", encoding="utf-8")
    saved = [{k: v for k, v in amount(value, period).items() if k != "status"}
             for value, period in ((1400, "month"), (33600, "total"))]
    session = SessionLocal()
    try:
        source = Source(name="Test format", url="https://test-format.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        now = datetime.now(UTC)
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                             content_hash="d" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
        row = Scholarship(
            name="Test format", source_id=source.id, countries=["SE"], degrees=["master"],
            nationality_scope="all", nationalities=[],
            extracted={"amounts": saved, "windows": [],
                       "verification": {"deadlines": [], "amounts": ["supported"] * 2, "issues": []},
                       "meta": {"snapshots": ["d" * 64], "prompts": [], "model": "fake"}},
        )
        session.add(row)
        session.flush()
        recheck_rules(session, [source.id])
        session.refresh(row)
        assert row.extracted["amounts"] == saved[:1]
    finally:
        session.rollback()
        session.close()
