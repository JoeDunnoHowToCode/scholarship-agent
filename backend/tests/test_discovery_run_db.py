"""三種發掘任務（ADR-080、083），在真的資料庫上跑：假的 AI、假的網頁，交易裡跑完就復原。"""

from datetime import UTC, datetime
from typing import Any, Self

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm.base import ChatMessage, ToolCall, ToolSpec, Turn
from app.features.discovery.models import University
from app.features.discovery.run import Deps, run_new_url, run_search, run_university
from app.features.discovery.tools import Page, SearchHit, Toolbox
from app.features.sources.links import Link
from app.features.sources.models import Discovery, Source, SourceKind, SourceStatus
from app.shared.db import SessionLocal

NOW = datetime.now(UTC)


class NoCommit:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def commit(self) -> None:
        self.session.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.session, name)


class Script:
    """照劇本：每一步呼叫一個工具，劇本用完就回答「完成」。"""

    def __init__(self, calls: list[tuple[str, dict[str, Any]]]) -> None:
        self.calls = calls

    def step(self, messages: list[ChatMessage], tools: list[ToolSpec]) -> Turn:
        if not self.calls:
            return Turn(ChatMessage("assistant", "完成"), 1, 1, 0.0)
        name, args = self.calls.pop(0)
        return Turn(ChatMessage("assistant", "", [ToolCall(f"c-{name}", name, args)]), 1, 1, 0.0)


PAGES = {
    "https://test-uni.example": Page("https://test-uni.example", "Test University", [Link("https://test-uni.example/scholarships", "Scholarships")]),
    "https://new-cyber.example/": Page("https://new-cyber.example/", "CyberMACS – Master of Applied Cybersecurity", []),
}


def deps(session: Session, calls: list[tuple[str, dict[str, Any]]]) -> Deps:
    shared = NoCommit(session)
    hits = [SearchHit("Gov scholarship", "https://test-gov.example/s", "for master students"),
            SearchHit("CyberMACS", "https://new-cyber.example/", "official site")]

    def toolbox(start_urls: list[str], max_submissions: int) -> Toolbox:
        return Toolbox(lambda q: hits, lambda url: PAGES[url], 10, start_urls, max_submissions)

    script = Script(calls)
    return Deps(make_llm=lambda run_id: script, toolbox=toolbox, read=lambda url: PAGES[url],
                max_cost_usd=1.0, sessions=lambda: shared)  # type: ignore[arg-type, return-value]


def test_university_task_turns_submissions_into_candidates() -> None:
    session = SessionLocal()
    try:
        school = University(country="GB", name="Test University", homepage="https://test-uni.example",
                            source_url="https://register-api.officeforstudents.org.uk/api/Provider")
        session.add(school)
        session.flush()
        calls = [("read_page", {"url": "https://test-uni.example"}),
                 ("submit", {"url": "https://test-uni.example/scholarships", "reason": "國際碩士獎學金"})]
        assert run_university(deps(session, calls), school.id, NOW) == 1
        source = session.scalars(select(Source).where(Source.url == "https://test-uni.example/scholarships")).one()
        assert (source.status, source.kind, source.discovery) == (SourceStatus.CANDIDATE, SourceKind.UNIVERSITY, Discovery.SEARCH)
        assert source.agent_run_id is not None
        assert (school.last_searched_at, school.last_result) == (NOW, "done")
    finally:
        session.rollback()
        session.close()


def test_search_runs_once_per_week() -> None:
    session = SessionLocal()
    try:
        calls = [("search", {"query": "UK government master scholarship Taiwan"}),
                 ("submit", {"url": "https://test-gov.example/s", "reason": "政府獎學金"})]
        first = run_search(deps(session, calls), NOW)
        assert first == 1
        assert session.scalars(select(Source).where(Source.url == "https://test-gov.example/s")).one().kind == SourceKind.INSTITUTION
        assert run_search(deps(session, []), NOW) is None  # 同一週不再搜尋
    finally:
        session.rollback()
        session.close()


def test_new_url_task_replaces_a_matching_url_and_waits_7_days() -> None:
    session = SessionLocal()
    try:
        source = Source(name="Master of Applied Cybersecurity", url="https://old-cyber.example/", kind=SourceKind.UNIVERSITY,
                        fail_days=5, unreachable_since=NOW.date())
        session.add(source)
        session.flush()
        calls = [("search", {"query": "Master of Applied Cybersecurity Erasmus Mundus"}),
                 ("read_page", {"url": "https://new-cyber.example/"}),
                 ("submit", {"url": "https://new-cyber.example/", "reason": "官方網站"})]
        result = run_new_url(deps(session, calls), source.id, NOW)
        assert result is not None
        kind, name, detail = result
        assert (kind, name) == ("replaced", "Master of Applied Cybersecurity")
        assert "https://old-cyber.example/" in detail and "https://new-cyber.example/" in detail
        assert (source.url, source.unreachable_since) == ("https://new-cyber.example/", None)
        assert run_new_url(deps(session, []), source.id, NOW) is None  # 7 天內不再找
    finally:
        session.rollback()
        session.close()
