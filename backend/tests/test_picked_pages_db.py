"""AI 從首頁挑的子頁照順序存下來，第一個當獎學金的官網連結（ADR-113，總檢查 B1 選 B）。

真的資料庫，交易裡跑完就復原；快照檔寫到暫存資料夾，不碰 backend/data/snapshots/。
"""

from pathlib import Path

import pytest

from app.core.fetch.base import FetchResult
from app.features.sources import fetch
from app.features.sources.links import Link
from app.features.sources.models import Source, SourceKind
from app.shared.db import SessionLocal

HOME = "https://test-picks.example/"
PICKS = ["https://test-picks.example/costs-and-financial-aid/", "https://test-picks.example/how-to-apply/"]


class Site:
    """假的網站：每一頁都回一樣的 HTML，首頁上有兩個連結。"""

    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        html = f'<html><body><a href="{PICKS[0]}">Costs</a><a href="{PICKS[1]}">Apply</a><p>{url}</p></body></html>'
        return FetchResult(url, 200, html.encode(), "text/html; charset=utf-8", None, None)


def picker(name: str, url: str, links: list[Link]) -> list[str]:
    return list(PICKS)  # AI 挑的順序：獎學金頁在前


def test_the_pages_the_ai_picks_are_kept_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch, "SNAPSHOT_DIR", tmp_path)
    session = SessionLocal()
    try:
        source = Source(name="Test picks", url=HOME, kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        fetch.fetch_source(session, Site(), source, picker)  # type: ignore[arg-type]
        assert source.picked_urls == PICKS
    finally:
        session.rollback()
        session.close()


def test_a_catalogue_scholarship_links_to_the_first_picked_page(tmp_path: Path) -> None:
    # 總檢查 B1：目錄來的 214 筆有 184 筆只連到學程首頁。agent 找到的網址本身就是獎學金頁，照舊
    from datetime import UTC, datetime

    from app.features.scholarships.extract import extract_source
    from app.features.scholarships.models import main_of
    from app.features.sources.models import Discovery, Snapshot
    from tests.test_extract_build import DRAFT, FakeLLM

    page = tmp_path / "page.html"
    page.write_text("<html><body><p>Erasmus Mundus scholarships</p></body></html>", encoding="utf-8")
    session = SessionLocal()
    try:
        links = {}
        for discovery, url in ((Discovery.CATALOGUE, HOME), (Discovery.SEARCH, "https://test-picks.example/funding")):
            source = Source(name=f"Test {discovery.value}", url=url, kind=SourceKind.UNIVERSITY, discovery=discovery,
                            picked_urls=PICKS)
            session.add(source)
            session.flush()
            now = datetime.now(UTC)
            session.add(Snapshot(source_id=source.id, url=url, fetched_at=now, seen_at=now, content_hash="7" * 64,
                                 file_path=str(page), http_status=200, etag=None, last_modified=None))
            session.flush()
            extract_source(session, FakeLLM(DRAFT), source)  # type: ignore[arg-type]
            links[discovery] = session.scalars(main_of(source.id)).one().official_url
        assert links == {Discovery.CATALOGUE: PICKS[0], Discovery.SEARCH: "https://test-picks.example/funding"}
    finally:
        session.rollback()
        session.close()
