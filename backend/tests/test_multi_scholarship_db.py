"""一頁有幾個獎學金就存幾筆（A1 C，ADR-108）。真的資料庫，交易裡跑完就復原。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.scholarships.extract import extract_source
from app.features.scholarships.models import Scholarship
from app.features.sources.models import Snapshot, Source, SourceKind
from app.shared.db import SessionLocal
from tests.test_extract_build import PAGE, FakeLLM


def scholarship(source_id: int, key: str) -> Scholarship:
    return Scholarship(name=f"Test {key}", source_id=source_id, key=key, countries=["FR"], degrees=["master"],
                       nationality_scope="all", nationalities=[], extracted={})


def source_with_page(session: Session, tmp_path: Path, page: str = PAGE) -> Source:
    path = tmp_path / "page.html"
    path.write_text(page, encoding="utf-8")
    source = Source(name="Test multi page", url="https://test-multi-page.example/", kind=SourceKind.UNIVERSITY)
    session.add(source)
    session.flush()
    now = datetime.now(UTC)
    session.add(Snapshot(source_id=source.id, url=source.url, fetched_at=now, seen_at=now,
                         content_hash="8" * 64, file_path=str(path), http_status=200, etag=None, last_modified=None))
    session.flush()
    return source


def test_one_source_can_hold_several_scholarships_with_different_keys() -> None:
    # 主角的 key 固定是 main（既有資料遷移後都是 main）；同一頁其他獎學金用正規化的名稱
    session = SessionLocal()
    try:
        source = Source(name="Test multi", url="https://test-multi.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        session.add_all([scholarship(source.id, "main"), scholarship(source.id, "regionalgrant")])
        session.flush()
        session.add(scholarship(source.id, "regionalgrant"))
        with pytest.raises(IntegrityError):
            session.flush()  # 同一來源、同一個 key 只能有一筆
    finally:
        session.rollback()
        session.close()


def test_reextracting_the_page_updates_its_main_scholarship(tmp_path: Path) -> None:
    # 同一來源已經有其他獎學金時，重抽主角要更新 key=main 那一筆，不能隨便拿到第一筆
    session = SessionLocal()
    try:
        source = source_with_page(session, tmp_path)
        other = scholarship(source.id, "erasmusgrant")  # 依 (source_id, key) 索引排序時排在 main 前面
        main = scholarship(source.id, "main")
        session.add_all([other, main])
        session.flush()
        extract_source(session, FakeLLM(), source)  # type: ignore[arg-type]
        assert main.name == "Test Global Scholarship"
        assert other.name == "Test erasmusgrant"
    finally:
        session.rollback()
        session.close()
