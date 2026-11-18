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
