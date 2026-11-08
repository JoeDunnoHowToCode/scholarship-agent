"""候選來源進出資料庫（ADR-078），在真的資料庫上跑：交易裡跑完就復原。"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.costs.usage import TAIPEI
from app.features.discovery.candidates import EMPTY_LIMIT, WEEKLY_DECISIONS
from app.features.discovery.intake import (
    add_candidates,
    decide_candidate,
    digest_items,
    pending_candidate_ids,
    review_after_extraction,
    track_extraction,
)
from app.features.discovery.tools import Submission
from app.features.pipeline.jobs import due_source_ids
from app.features.scholarships.models import Cycle, Scholarship
from app.features.sources.models import Discovery, Source, SourceKind, SourceStatus
from app.shared.db import SessionLocal

NOW = datetime.now(UTC)


def candidate(session: Session, url: str) -> Source:
    add_candidates(session, [Submission(url, "獎學金頁")], SourceKind.UNIVERSITY, None)
    session.flush()
    source = session.scalars(select(Source).where(Source.url == url)).first()
    assert source is not None, "提交應該變成一筆候選來源"
    return source


def scholarship(session: Session, source: Source, countries: list[str], name: str = "Lund Global Scholarship") -> None:
    row = Scholarship(
        name=name, source_id=source.id, countries=countries, degrees=["master"],
        nationality_scope="all", nationalities=[], extracted={"verification": {"degrees": "supported"}},
    )
    session.add(row)
    session.flush()
    session.add(Cycle(scholarship_id=row.id, closes_at=NOW + timedelta(days=60), status="upcoming"))
    session.flush()


def test_submissions_become_candidates_once() -> None:
    session = SessionLocal()
    try:
        existing = session.scalars(select(Source.url).limit(1)).one()
        added = add_candidates(
            session, [Submission("https://test-candidate.example/s", "獎學金頁"), Submission(existing, "已經有了")],
            SourceKind.UNIVERSITY, None,
        )
        session.flush()
        assert added == 1  # 已經有的網址略過
        source = session.scalars(select(Source).where(Source.url == "https://test-candidate.example/s")).one()
        assert (source.status, source.discovery, source.kind, source.name) == (
            SourceStatus.CANDIDATE, Discovery.SEARCH, SourceKind.UNIVERSITY, "https://test-candidate.example/s",
        )
    finally:
        session.rollback()
        session.close()


def test_pending_candidates_respect_the_weekly_budget() -> None:
    session = SessionLocal()
    try:
        first = candidate(session, "https://test-a.example/s")
        second = candidate(session, "https://test-b.example/s")
        pending = pending_candidate_ids(session, NOW)
        assert first.id in pending and second.id in pending
        assert pending.index(first.id) < pending.index(second.id)  # 最舊的先
        # 這 7 天已經決定了 50 個：今天一個都不評
        for n in range(WEEKLY_DECISIONS):
            session.add(Source(
                name=f"decided {n}", url=f"https://test-decided-{n}.example/", kind=SourceKind.UNIVERSITY,
                discovery=Discovery.SEARCH, status=SourceStatus.REJECTED, decided_at=NOW - timedelta(days=1),
            ))
        session.flush()
        assert pending_candidate_ids(session, NOW) == []
    finally:
        session.rollback()
        session.close()


def test_candidates_are_approved_or_rejected_by_the_rules() -> None:
    session = SessionLocal()
    try:
        good = candidate(session, "https://test-good.example/s")
        scholarship(session, good, ["SE"])
        assert decide_candidate(session, good, NOW) == "approved"
        assert (good.status, good.enabled, good.name) == (SourceStatus.APPROVED, True, "Lund Global Scholarship")
        assert good.decided_at == NOW

        far = candidate(session, "https://test-far.example/s")
        scholarship(session, far, ["US"], name="US Scholarship")
        assert decide_candidate(session, far, NOW) == "rejected"
        assert (far.status, far.enabled, far.review_note) == (SourceStatus.REJECTED, False, "留學國家不在歐洲")

        empty = candidate(session, "https://test-empty.example/s")
        assert decide_candidate(session, empty, NOW) == "rejected"
        assert empty.review_note == "沒有抽出獎學金"

        added, rejected, _ = digest_items(session, NOW)
        assert ("Lund Global Scholarship", "https://test-good.example/s") in added
        assert ("US Scholarship", "留學國家不在歐洲") in rejected
    finally:
        session.rollback()
        session.close()


def test_agent_sources_are_disabled_after_three_empty_extractions() -> None:
    session = SessionLocal()
    try:
        source = candidate(session, "https://test-decay.example/s")
        scholarship(session, source, ["US"], name="Moved programme")  # 規則不過：算抽不到有效獎學金
        source.status = SourceStatus.APPROVED
        results = [track_extraction(session, source, NOW) for _ in range(EMPTY_LIMIT)]
        assert results == [False] * (EMPTY_LIMIT - 1) + [True]
        assert (source.enabled, source.disabled_at, source.review_note) == (
            False, NOW, f"連續 {EMPTY_LIMIT} 次抽不到有效獎學金",
        )
        _, _, disabled = digest_items(session, NOW)
        assert ("Moved programme", f"連續 {EMPTY_LIMIT} 次抽不到有效獎學金") in disabled
    finally:
        session.rollback()
        session.close()


def test_daily_flow_checks_candidates_and_reviews_them_after_extraction() -> None:
    session = SessionLocal()
    try:
        source = candidate(session, "https://test-daily.example/s")
        # 候選排進今天的檢查
        assert source.id in due_source_ids(session, NOW.astimezone(TAIPEI).date())
        scholarship(session, source, ["FI"])
        # 抽完：候選就決定
        assert review_after_extraction(session, source, "類別 1、文件 3", NOW) == "approved"
        # 已加入的 agent 來源：內容沒變、只有無關內容變了，都不算一次抽取
        assert review_after_extraction(session, source, "unchanged", NOW) is None
        assert review_after_extraction(session, source, "noise", NOW) is None
        assert source.empty_extractions == 0
        # 種子和目錄來的來源不管
        seed = session.scalars(select(Source).where(Source.discovery != Discovery.SEARCH).limit(1)).one()
        assert review_after_extraction(session, seed, "類別 1", NOW) is None
    finally:
        session.rollback()
        session.close()
