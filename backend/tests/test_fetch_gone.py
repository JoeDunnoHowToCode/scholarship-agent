"""首頁不見了（11-09 使用者選 C）：首頁回 404 或 410，這天算失敗、不重試；子頁 404 照舊跳過。"""

import httpx
import pytest

from app.core.fetch.base import FetchResult, PageGone
from app.features.pipeline.errors import classify
from app.features.sources.fetch import fetch_source
from app.features.sources.models import Source, SourceKind
from app.shared.db import SessionLocal


class Gone:
    """假的抓取器：每一頁都回指定的狀態碼。"""

    def __init__(self, status: int) -> None:
        self.status = status

    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        request = httpx.Request("GET", url)
        raise httpx.HTTPStatusError(str(self.status), request=request, response=httpx.Response(self.status, request=request))


@pytest.mark.parametrize("status", [404, 410])
def test_a_missing_homepage_fails_the_day_without_retry(status: int) -> None:
    session = SessionLocal()
    try:
        source = Source(name="Gone programme", url="https://test-gone.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        with pytest.raises(PageGone) as raised:
            fetch_source(session, Gone(status), source)  # type: ignore[arg-type]
        assert raised.value.status == status
        assert classify(raised.value) == "fail"  # 當天算失敗、不重試；連續 3 天就標記抓不到
    finally:
        session.rollback()
        session.close()
