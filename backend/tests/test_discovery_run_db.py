"""三種發掘任務（ADR-080、083），在真的資料庫上跑：假的 AI、假的網頁，交易裡跑完就復原。"""

from datetime import UTC, datetime, timedelta
from typing import Any, Self

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.llm.base import ChatMessage, ToolCall, ToolSpec, Turn
from app.features.costs.recorder import MonthlyCapError
from app.features.discovery.models import AgentRun, University
from app.features.discovery.run import (
    Deps,
    discover,
    new_url_targets,
    run_new_url,
    run_search,
    run_university,
)
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
        # 真的資料庫裡可能已經有本週的搜尋紀錄（例如手動實跑過）：在交易裡先移到 8 天前，測完復原
        session.execute(update(AgentRun).where(AgentRun.task == "search").values(started_at=NOW - timedelta(days=8)))
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


def test_new_url_targets_are_unreachable_enabled_and_not_searched_this_week() -> None:
    session = SessionLocal()
    try:
        due = Source(name="T due", url="https://t-due.example/", kind=SourceKind.UNIVERSITY, unreachable_since=NOW.date(),
                     last_error="gaierror: nodename nor servname provided")  # 網站不在了才找（11-09 使用者選 B）
        off = Source(name="T off", url="https://t-off.example/", kind=SourceKind.UNIVERSITY, unreachable_since=NOW.date(), enabled=False)
        fine = Source(name="T fine", url="https://t-fine.example/", kind=SourceKind.UNIVERSITY)
        recent = Source(name="T recent", url="https://t-recent.example/", kind=SourceKind.UNIVERSITY, unreachable_since=NOW.date())
        session.add_all([due, off, fine, recent])
        session.flush()
        session.add(AgentRun(task="new_url", target=f"source:{recent.id}", started_at=NOW))
        session.flush()
        targets = new_url_targets(session, NOW)
        assert due.id in targets
        assert not {off.id, fine.id, recent.id} & set(targets)
    finally:
        session.rollback()
        session.close()


class Exploding:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def step(self, messages: list[ChatMessage], tools: list[ToolSpec]) -> Turn:
        raise self.error


def test_discover_skips_a_broken_task_but_stops_at_the_monthly_cap() -> None:
    session = SessionLocal()
    try:
        schools = [University(country="SE", name=f"T{n}", homepage=f"https://t-school-{n}.example",
                              source_url="https://www.uka.se/x") for n in range(2)]
        session.add_all(schools)
        session.flush()
        ids = [s.id for s in schools]
        broken = deps(session, [])
        broken.make_llm = lambda run_id: Exploding(RuntimeError("網站格式怪"))  # type: ignore[assignment, return-value]
        summary = discover(broken, NOW, ids, search=False, new_urls=[])
        assert (summary.schools, summary.errors, summary.stopped) == (2, 2, None)  # 一般錯誤：跳過、繼續下一所
        capped = deps(session, [])
        capped.make_llm = lambda run_id: Exploding(MonthlyCapError("本月 AI 已達每月上限"))  # type: ignore[assignment, return-value]
        summary = discover(capped, NOW, ids, search=False, new_urls=[])
        assert summary.stopped is not None and "上限" in summary.stopped
        assert summary.schools == 0  # 第一所就停下，不再跑第二所
    finally:
        session.rollback()
        session.close()


def test_new_url_task_reports_a_superseded_source() -> None:
    session = SessionLocal()
    try:
        session.add(Source(name="CyberMACS new", url="https://new-cyber.example/", kind=SourceKind.UNIVERSITY))
        old = Source(name="Master of Applied Cybersecurity", url="https://old-cyber-b.example/", kind=SourceKind.UNIVERSITY,
                     unreachable_since=NOW.date())
        session.add(old)
        session.flush()
        calls = [("search", {"query": "Master of Applied Cybersecurity"}),
                 ("submit", {"url": "https://new-cyber.example/", "reason": "官方網站"})]
        result = run_new_url(deps(session, calls), old.id, NOW)
        assert result is not None and result[0] == "superseded"
        assert old.enabled is False
    finally:
        session.rollback()
        session.close()


def test_new_urls_are_only_searched_for_gone_sites_outside_the_catalogue() -> None:
    # 11-09 使用者選 B、D：網站不在了才找；EACEA 目錄來的學程以目錄為準，不派 agent
    session = SessionLocal()
    try:
        def marked(name: str, error: str, discovery: Discovery = Discovery.SEED) -> Source:
            return Source(name=name, url=f"https://{name}.example/", kind=SourceKind.UNIVERSITY,
                          unreachable_since=NOW.date(), last_error=error, discovery=discovery)

        gone = marked("t-gone", "gaierror: nodename nor servname provided")
        missing = marked("t-404", "PageGone: 首頁不存在（404）：https://t-404.example/")
        slow = marked("t-slow", "httpx.ConnectTimeout: timed out")
        listed = marked("t-cat", "gaierror: nodename nor servname provided", Discovery.CATALOGUE)
        session.add_all([gone, missing, slow, listed])
        session.flush()
        targets = set(new_url_targets(session, NOW))
        assert {gone.id, missing.id} <= targets
        assert not {slow.id, listed.id} & targets
    finally:
        session.rollback()
        session.close()
