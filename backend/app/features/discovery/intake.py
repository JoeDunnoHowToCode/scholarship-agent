"""候選來源進出資料庫（ADR-078）：提交 → 候選 → 抽取後決定加入或排除；加入後持續檢查品質。

規則本身在 candidates.py（純邏輯）；這裡負責讀寫 sources。呼叫的人負責 commit。
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.features.costs.usage import TAIPEI
from app.features.discovery.candidates import (
    EMPTY_LIMIT,
    Facts,
    budget,
    judge,
    next_empty,
)
from app.features.discovery.tools import Submission
from app.features.notifications.generate import add_system_event
from app.features.pipeline.report import discovery_digest_message
from app.features.profiles.service import CURRENT_USER_ID
from app.features.scholarships.models import Scholarship
from app.features.sources.models import Discovery, Source, SourceKind, SourceStatus

WEEK = timedelta(days=7)
# extract_source 的這些摘要代表這次沒有真的重抽（ADR-079）
NOT_EXTRACTED = frozenset({"unchanged", "noise"})


def add_candidates(
    session: Session, submissions: list[Submission], kind: SourceKind, agent_run_id: int | None
) -> int:
    """agent 的提交變成候選來源；已經有的網址（包括已排除的）略過。回傳新增幾個。"""
    added = 0
    for submission in submissions:
        if session.scalar(select(Source.id).where(Source.url == submission.url)) is not None:
            continue
        # 名稱先用網址；抽取出獎學金名稱後，決定時再換成獎學金名稱
        session.add(Source(
            name=submission.url, url=submission.url, kind=kind, discovery=Discovery.SEARCH,
            status=SourceStatus.CANDIDATE, agent_run_id=agent_run_id,
        ))
        session.flush()  # 馬上寫入：同一批裡重複的網址，下一圈就查得到
        added += 1
    return added


def pending_candidate_ids(session: Session, now: datetime) -> list[int]:
    """今天要評分的候選（最舊的先），不超過每週上限。"""
    decided = session.scalar(
        select(func.count()).select_from(Source).where(
            Source.discovery == Discovery.SEARCH, Source.decided_at >= now - WEEK
        )
    )
    left = budget(int(decided or 0))
    if left == 0:
        return []  # 超過的提交留在候選，下週再評
    return list(session.scalars(
        select(Source.id)
        .where(Source.status == SourceStatus.CANDIDATE, Source.enabled.is_(True), Source.manual_reason.is_(None))
        .order_by(Source.created_at, Source.id)
        .limit(left)
    ))


def decide_candidate(session: Session, source: Source, now: datetime) -> str:
    """候選抽取完之後：四條規則都過就加入（approved），否則排除（rejected）並記下原因。"""
    row = _scholarship(session, source)
    reasons = ["沒有抽出獎學金"] if row is None else judge(_facts(row), now)
    source.decided_at = now
    if row is not None:
        source.name = row.name
    if reasons:
        source.status, source.enabled, source.review_note = SourceStatus.REJECTED, False, "；".join(reasons)
        return "rejected"
    source.status, source.review_note = SourceStatus.APPROVED, None
    return "approved"


def track_extraction(session: Session, source: Source, now: datetime) -> bool:
    """agent 加的來源每次重新抽取後：更新連續抽不到的次數，到上限就停用。回傳這次有沒有停用。"""
    row = _scholarship(session, source)
    if row is not None:
        source.name = row.name  # 名稱跟著最新的抽取結果（通知和摘要用）
    valid = row is not None and not judge(_facts(row), now)
    source.empty_extractions, disable = next_empty(source.empty_extractions, valid)
    if disable:
        source.enabled, source.disabled_at = False, now
        source.review_note = f"連續 {EMPTY_LIMIT} 次抽不到有效獎學金"
    return disable


def digest_items(
    session: Session, now: datetime
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """最近 7 天：加入（名稱, 網址）、排除（名稱, 原因）、停用（名稱, 原因）。"""
    agent = (Source.discovery == Discovery.SEARCH,)
    decided = Source.decided_at >= now - WEEK
    added = session.execute(
        select(Source.name, Source.url).where(*agent, decided, Source.status == SourceStatus.APPROVED).order_by(Source.id)
    ).tuples().all()
    rejected = session.execute(
        select(Source.name, Source.review_note).where(*agent, decided, Source.status == SourceStatus.REJECTED)
        .order_by(Source.id)
    ).tuples().all()
    disabled = session.execute(
        select(Source.name, Source.review_note).where(*agent, Source.disabled_at >= now - WEEK).order_by(Source.id)
    ).tuples().all()
    return (
        [(name, url) for name, url in added],
        [(name, note or "") for name, note in rejected],
        [(name, note or "") for name, note in disabled],
    )


def _scholarship(session: Session, source: Source) -> Scholarship | None:
    return session.scalars(
        select(Scholarship).where(Scholarship.source_id == source.id).options(selectinload(Scholarship.cycles))
    ).first()


def _facts(row: Scholarship) -> Facts:
    return Facts(
        countries=list(row.countries),
        degrees=list(row.degrees),
        degrees_check=row.extracted.get("verification", {}).get("degrees"),
        nationality_scope=row.nationality_scope,
        nationalities=list(row.nationalities),
        closes=[cycle.closes_at for cycle in row.cycles if not cycle.estimated],  # 程式預估的不算
    )


def review_after_extraction(session: Session, source: Source, summary: str, now: datetime) -> str | None:
    """每天的來源工作抽完後叫它：候選就決定加入或排除；agent 加的來源真的重抽了就檢查品質。

    回傳 approved、rejected、disabled，或 None（不是 agent 的來源、或這次沒有重抽）。
    """
    if source.discovery != Discovery.SEARCH:
        return None  # 種子、目錄來的來源不受這套規則管
    if source.status == SourceStatus.CANDIDATE:
        return decide_candidate(session, source, now)
    if summary in NOT_EXTRACTED:
        return None  # 內容沒變、只有無關內容變了：不算一次抽取
    return "disabled" if track_extraction(session, source, now) else None


def add_weekly_digest(session: Session, now: datetime) -> bool:
    """這週（台灣時間的 ISO 週）第一次收尾時，加一則發掘的每週摘要；最近 7 天沒有動靜就不送。回傳有沒有加。"""
    added, rejected, disabled = digest_items(session, now)
    if not (added or rejected or disabled):
        return False  # 「Claude 自行決定」第 25 點：沒有動靜就不打擾
    year, week, _ = now.astimezone(TAIPEI).date().isocalendar()
    title, lines = discovery_digest_message(added, rejected, disabled)
    # 去重鍵用週次：同一週不管收尾幾次都只送一則
    return add_system_event(session, CURRENT_USER_ID, f"discovery:{year}-W{week:02d}", title, lines, now)
