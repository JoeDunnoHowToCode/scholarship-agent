"""申請方式存進資料表；每天的 refresh 寫下沒有申請期的原因（ADR-119）。真的資料庫，交易裡跑完就復原。"""

from datetime import UTC, datetime
from pathlib import Path

from app.features.scholarships.cycles import refresh
from app.features.scholarships.models import Scholarship
from app.features.sources.models import Source, SourceKind
from app.shared.db import SessionLocal

NOW = datetime.now(UTC)


def test_refresh_records_why_a_scholarship_has_no_application_period() -> None:
    session = SessionLocal()
    try:
        source = Source(name="Test no date", url="https://test-no-date.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        row = Scholarship(name="Test automatic bursary", source_id=source.id,
                          extracted={"how_to_apply": "automatic", "windows": []})
        session.add(row)
        session.flush()
        refresh(session, NOW)
        assert row.no_date_reason == "no_application"
    finally:
        session.rollback()
        session.close()


def test_the_extraction_stores_how_to_apply(tmp_path: Path) -> None:
    from app.features.scholarships.extract import extract_source
    from app.features.scholarships.models import main_of
    from app.features.sources.models import Snapshot
    from tests.test_extract_build import DRAFT, FakeLLM

    quote = "There is no need to apply. You will automatically receive the scholarship"
    page = tmp_path / "page.html"
    page.write_text(f"<html><body><p>{quote}.</p></body></html>", encoding="utf-8")
    session = SessionLocal()
    try:
        source = Source(name="Test how to apply", url="https://test-how-to-apply.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=NOW, seen_at=NOW, content_hash="6" * 64,
                             file_path=str(page), http_status=200, etag=None, last_modified=None))
        session.flush()
        draft = DRAFT.model_copy(update={"how_to_apply": "automatic", "how_to_apply_evidence": quote})
        extract_source(session, FakeLLM(draft), source)  # type: ignore[arg-type]
        assert session.scalars(main_of(source.id)).one().how_to_apply == "automatic"
    finally:
        session.rollback()
        session.close()
