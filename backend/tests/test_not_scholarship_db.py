"""頁面沒有提供任何獎學金就停用來源（A2 C，ADR-107）。用假的 AI，真的資料庫，交易裡跑完就復原。"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.scholarships.extract import extract_source
from app.features.scholarships.models import Scholarship, ScholarshipStatus
from app.features.sources.models import Snapshot, Source, SourceKind
from app.shared.db import SessionLocal
from tests.test_extract_build import DRAFT, FakeLLM

PAGE = "<html><body><h1>Test School</h1><p>The school does not offer scholarships or tuition waivers.</p></body></html>"


def run(session: Session, tmp_path: Path, evidence: str) -> tuple[Source, Scholarship]:
    page = tmp_path / "page.html"
    page.write_text(PAGE, encoding="utf-8")
    source = Source(name="Test not scholarship", url="https://test-not-scholarship.example/",
                    kind=SourceKind.UNIVERSITY)
    session.add(source)
    session.flush()
    now = datetime.now(UTC)
    session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                         content_hash="9" * 64, file_path=str(page), http_status=200, etag=None, last_modified=None))
    session.flush()
    draft = DRAFT.model_copy(update={"not_scholarship": True, "not_scholarship_evidence": evidence})
    extract_source(session, FakeLLM(draft), source)  # type: ignore[arg-type]
    row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).one()
    return source, row


def test_a_page_without_any_scholarship_disables_its_source(tmp_path: Path) -> None:
    session = SessionLocal()
    try:
        source, row = run(session, tmp_path, "The school does not offer scholarships or tuition waivers.")
        assert source.enabled is False and source.disabled_at is not None
        assert (source.review_note or "").startswith("判斷不是獎學金")
        assert row.status == ScholarshipStatus.ARCHIVED  # 預設的列表看不到，詳細頁照樣看得到
    finally:
        session.rollback()
        session.close()


def test_the_quote_must_be_in_the_page_before_a_source_is_disabled(tmp_path: Path) -> None:
    # 關鍵欄位附逐字引用，程式確認引用真的在原文裡；引用對不上就不停用
    session = SessionLocal()
    try:
        source, row = run(session, tmp_path, "No funding is available this year.")
        assert source.enabled is True and row.status == ScholarshipStatus.ACTIVE
    finally:
        session.rollback()
        session.close()


def test_the_daily_report_finds_sources_disabled_as_not_scholarships_since_the_run_started(tmp_path: Path) -> None:
    from app.features.scholarships.extract import disabled_as_not_scholarship

    session = SessionLocal()
    try:
        started = datetime.now(UTC)
        source, _ = run(session, tmp_path, "The school does not offer scholarships or tuition waivers.")
        assert source.name in disabled_as_not_scholarship(session, started)
        assert source.name not in disabled_as_not_scholarship(session, datetime.now(UTC))
    finally:
        session.rollback()
        session.close()


def test_the_daily_refresh_does_not_recall_a_scholarship_without_any_cycle(tmp_path: Path) -> None:
    # 每天的 refresh 只在有開放中或即將開放的申請期時喚回（cycles.refresh 的註解）；
    # 一個申請期都沒有的已封存獎學金（例如判斷不是獎學金而封存的）要維持封存
    from app.features.scholarships.cycles import refresh

    session = SessionLocal()
    try:
        _, row = run(session, tmp_path, "The school does not offer scholarships or tuition waivers.")
        assert row.cycles == [] and row.status == ScholarshipStatus.ARCHIVED
        refresh(session, datetime.now(UTC))
        assert row.status == ScholarshipStatus.ARCHIVED
    finally:
        session.rollback()
        session.close()


def test_a_source_disabled_as_not_a_scholarship_is_reenabled_when_the_judgment_changes(tmp_path: Path) -> None:
    # 判斷可能錯（11-16 重抽有 16 個，多半是「這一屆沒有」或壞掉的網頁）；改了提示詞重抽、不再判斷成不是獎學金時，
    # 程式自己停用的來源要自己打開，獎學金改回使用中。使用者在設定頁停用的不動
    session = SessionLocal()
    try:
        source, row = run(session, tmp_path, "The school does not offer scholarships or tuition waivers.")
        assert source.enabled is False
        extract_source(session, FakeLLM(DRAFT), source, force=True)  # type: ignore[arg-type]
        assert (source.enabled, source.disabled_at, source.review_note) == (True, None, None)
        assert row.status == ScholarshipStatus.ACTIVE
    finally:
        session.rollback()
        session.close()
