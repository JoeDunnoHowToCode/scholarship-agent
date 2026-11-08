"""工具背後的實際做法：Tavily 用 httpx 的假伺服器測，讀網頁用假的抓取器，搜尋次數在真的資料庫上算。"""

import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from app.core.fetch.base import FetchResult
from app.features.discovery.models import AgentRun, AgentStep
from app.features.discovery.services import (
    fetch_page,
    searches_this_month,
    tavily_search,
)
from app.features.discovery.tools import SearchUnavailable
from app.shared.db import SessionLocal

KEY = SecretStr("tvly-test-key")


def client(status: int, body: dict[str, object], seen: list[httpx.Request]) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_tavily_search_sends_a_basic_search_and_parses_results() -> None:
    seen: list[httpx.Request] = []
    body = {"results": [{"title": "Lund Global Scholarship", "url": "https://lu.se/s", "content": "Tuition", "score": 0.9}]}
    hits = tavily_search(client(200, body, seen), KEY, "Lund scholarship")
    assert [(h.title, h.url, h.content) for h in hits] == [("Lund Global Scholarship", "https://lu.se/s", "Tuition")]
    assert len(seen) == 1
    sent = json.loads(seen[0].content)
    assert seen[0].headers["Authorization"] == "Bearer tvly-test-key"
    assert sent == {"query": "Lund scholarship", "search_depth": "basic", "max_results": 5}  # 基本搜尋，一次 1 點


@pytest.mark.parametrize("status", [401, 432, 433])
def test_tavily_refusals_stop_without_printing_the_key(status: int) -> None:
    with pytest.raises(SearchUnavailable) as raised:
        tavily_search(client(status, {"detail": "no"}, []), KEY, "q")
    assert str(status) in str(raised.value)
    assert "tvly-test-key" not in str(raised.value)  # 錯誤訊息不能帶出金鑰


class FakeFetcher:
    def get(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        html = b'<html><body><h1>Scholarships</h1><p>For master students.</p><a href="/apply">Apply</a></body></html>'
        return FetchResult(url + "#moved", 200, html, "text/html; charset=utf-8", None, None)


def test_fetch_page_returns_visible_text_and_links() -> None:
    page = fetch_page(FakeFetcher(), "https://lu.se/")
    assert page.url == "https://lu.se/#moved"
    assert "Scholarships" in page.text and "For master students." in page.text
    assert [link.url for link in page.links] == ["https://lu.se/apply"]


def test_searches_this_month_counts_search_tool_steps() -> None:
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        before = searches_this_month(session, now)
        run = AgentRun(task="smoke")
        session.add(run)
        session.flush()
        session.add_all([
            AgentStep(agent_run_id=run.id, number=1, kind="tool", tool="search", args={"query": "a"}, summary="x"),
            AgentStep(agent_run_id=run.id, number=2, kind="tool", tool="search", args={"query": "b"}, summary="x"),
            AgentStep(agent_run_id=run.id, number=2, kind="tool", tool="read_page", args={"url": "u"}, summary="x"),
        ])
        session.flush()
        assert searches_this_month(session, now) == before + 2
    finally:
        session.rollback()
        session.close()
