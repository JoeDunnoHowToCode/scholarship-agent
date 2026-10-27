"""獎學金列表與詳細頁的 API（第 9 天）：網頁的列表、詳細頁會呼叫這兩個端點。

列表一筆獎學金一列，分數用分數最高的類別（和第 8 天通知的 best_scores 一致）；
沒有搜尋字時，依時間狀態分組、同組依分數排（ADR-059）。
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import any_, exists, false, literal, select
from sqlalchemy.orm import Session, selectinload

from app.features.matching.models import Match
from app.features.matching.score import describe_cycle
from app.features.notifications.rules import describe_change
from app.features.profiles.service import CURRENT_USER_ID, get_profile
from app.features.scholarships import countries
from app.features.scholarships.cycles import is_stale
from app.features.scholarships.listing import list_order
from app.features.scholarships.models import (
    Change,
    Cycle,
    Requirement,
    Scholarship,
    ScholarshipCategory,
    ScholarshipStatus,
)
from app.features.scholarships.schemas import Degree
from app.features.search.find import next_deadline
from app.shared.db import get_session

# FastAPI 的依賴注入：每個請求自動拿到一個資料庫 Session
DbSession = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/api/scholarships", tags=["獎學金"])

TAIPEI = ZoneInfo("Asia/Taipei")
# 詳細頁只列會通知的欄位的變更（ADR-064）；其他欄位的紀錄雜訊多（docs/day-08.md 執行時發現第 6 點）
NOTIFIED_FIELDS = ("windows", "nationality_scope", "nationalities", "degrees")


class Country(BaseModel):
    """國碼與中文國名（ADR-054：台灣顯示為「台灣」）。"""

    code: str
    name: str


class ScholarshipRow(BaseModel):
    """列表的一列：一筆獎學金，分數用分數最高的類別。"""

    id: int
    name: str
    name_zh: str | None
    provider: str | None
    countries: list[Country]
    degrees: list[str]
    status: str  # active 使用中、archived 已封存
    stale: bool  # 資料過舊（ADR-058）
    next_deadline: datetime | None  # 還能申請的申請期裡最早的截止時間
    score: float | None  # 還沒評分（例如沒有個人資料）時是 None
    category: str | None
    group: Literal["pass", "unclear", "fail"] | None  # 時間狀態：還能申請、時間待確認、已截止或不適用
    time_reason: str | None
    unclear: list[str]  # 待確認的條件（nationality、degree）
    failed: list[str]  # 不符合的條件
    official_url: str | None


class ScholarshipList(BaseModel):
    rows: list[ScholarshipRow]
    scores_outdated: bool  # 個人資料改過，評分還在背景更新


class CycleOut(BaseModel):
    """一個申請期；description 和通知用同一種寫法，日期用原文的時區。"""

    description: str
    intake: str | None
    label: str | None
    opens_at: datetime | None
    closes_at: datetime
    timezone: str | None
    timezone_assumed: bool
    status: str  # estimated、upcoming、open、closed
    estimated: bool
    nationality_scope: str
    nationalities: list[Country]
    funding: str
    evidence: str | None
    verification: str | None


class CategoryOut(BaseModel):
    name: str
    quota: int | None
    degrees: list[str]
    countries: list[Country]
    eligibility: str | None
    degree_conditions: str | None
    quota_evidence: str | None
    degrees_evidence: str | None
    issues: list[str]  # 程式檢查發現的問題（ADR-045），沒有就是空清單


class RequirementOut(BaseModel):
    doc_type: str
    details: str | None
    required: bool | None
    count: int | None
    category: str | None  # 只有某個類別要交時才有
    evidence: str | None


class ScoreOut(BaseModel):
    """一個類別的評分；理由可能提到你的科系，只在本機的網頁顯示（ADR-063 只限制通知）。"""

    category: str
    total: float
    cap: int | None
    checks: dict[str, Any]
    sub_scores: dict[str, Any]
    unclear: list[str]
    failed: list[str]
    computed_at: datetime


class ChangeOut(BaseModel):
    changed_at: datetime
    text: str


class ScholarshipDetail(BaseModel):
    id: int
    name: str
    name_zh: str | None
    provider: str | None
    countries: list[Country]
    degrees: list[str]
    fields: list[str]
    coverage: str | None
    amount: str | None
    language_requirements: str | None
    other_eligibility: str | None
    requires_admission: bool | None
    nationality_scope: str
    nationalities: list[Country]
    nationality_conditions: str | None
    nationality_evidence: str | None
    nationality_check: str | None  # 驗證結果，例如 supported、catalogue（ADR-053）、quote_not_found
    degrees_evidence: str | None
    degrees_check: str | None
    official_url: str | None
    status: str
    stale: bool
    last_verified_at: datetime | None
    categories: list[CategoryOut]
    cycles: list[CycleOut]
    requirements: list[RequirementOut]
    scores: list[ScoreOut]
    changes: list[ChangeOut]


def country_list(codes: list[str]) -> list[Country]:
    return [Country(code=code, name=countries.chinese_name(code)) for code in codes]


def stale_of(row: Scholarship, today: date) -> bool:
    """資料過舊：已封存，而且最近一次真的截止日超過 24 個月（ADR-058，和每天的 refresh 同一個判斷）。"""
    latest = max((c.closes_at for c in row.cycles if not c.estimated), default=None)
    return row.status == ScholarshipStatus.ARCHIVED and latest is not None and is_stale(latest, today)


def start_of(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=UTC)


def best_matches(session: Session) -> dict[int, Match]:
    """每筆獎學金分數最高的評分（一筆獎學金常有好幾個類別）。"""
    best: dict[int, Match] = {}
    for match in session.scalars(select(Match).where(Match.user_id == CURRENT_USER_ID)):
        current = best.get(match.scholarship_id)
        if current is None or match.total > current.total:
            best[match.scholarship_id] = match
    return best


@router.get("")
def list_scholarships(
    session: DbSession,
    country: str | None = None,
    degree: Degree | None = None,
    open_only: bool = False,
    deadline_after: date | None = None,
    deadline_before: date | None = None,
) -> ScholarshipList:
    """篩選：留學國家、學位看獎學金本身；只看還能申請的、截止日範圍看真的（不是預估的）申請期。"""
    query = (
        select(Scholarship)
        # 只看代表的那筆（ADR-048），而且是從來源抽出來的
        .where(Scholarship.duplicate_of.is_(None), Scholarship.source_id.is_not(None))
        .options(selectinload(Scholarship.cycles))
    )
    if country:
        query = query.where(literal(country.upper()) == any_(Scholarship.countries))
    if degree:
        query = query.where(literal(degree) == any_(Scholarship.degrees))
    if open_only or deadline_after or deadline_before:
        cycle = select(Cycle.id).where(Cycle.scholarship_id == Scholarship.id, Cycle.estimated.is_(false()))
        if open_only:
            cycle = cycle.where(Cycle.status.in_(["open", "upcoming"]))
        if deadline_after:
            cycle = cycle.where(Cycle.closes_at >= start_of(deadline_after))
        if deadline_before:
            # 截止日當天也算：上限是隔天 0 點
            cycle = cycle.where(Cycle.closes_at < start_of(deadline_before + timedelta(days=1)))
        query = query.where(cycle.exists())
    best = best_matches(session)
    today = datetime.now(TAIPEI).date()
    rows = []
    for row in session.scalars(query):
        match = best.get(row.id)
        time_check = match.checks["time"] if match else None
        rows.append(
            ScholarshipRow(
                id=row.id,
                name=row.name,
                name_zh=row.name_zh,
                provider=row.provider,
                countries=country_list(row.countries),
                degrees=list(row.degrees),
                status=row.status.value,
                stale=stale_of(row, today),
                next_deadline=next_deadline(list(row.cycles)),
                score=match.total if match else None,
                category=match.category_name if match else None,
                group=time_check["result"] if time_check else None,
                time_reason=time_check["reason"] if time_check else None,
                unclear=list(match.unclear) if match else [],
                failed=list(match.failed) if match else [],
                official_url=row.official_url,
            )
        )
    rows.sort(key=lambda r: list_order(r.group, r.score))
    profile = get_profile(session, CURRENT_USER_ID)
    outdated = profile is not None and bool(
        session.scalar(
            select(exists().where(Match.user_id == CURRENT_USER_ID, Match.profile_version < profile.version))
        )
    )
    return ScholarshipList(rows=rows, scores_outdated=outdated)


@router.get("/{scholarship_id}")
def read_scholarship(scholarship_id: int, session: DbSession) -> ScholarshipDetail:
    row = session.scalars(
        select(Scholarship).where(Scholarship.id == scholarship_id).options(selectinload(Scholarship.cycles))
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="找不到這筆獎學金")
    extracted = row.extracted
    verification: dict[str, Any] = extracted.get("verification", {})
    flagged: dict[str, list[str]] = verification.get("categories", {})
    categories = [
        CategoryOut(
            name=c["name"],
            quota=c.get("quota"),
            degrees=c.get("degrees", []),
            countries=country_list(c.get("countries", [])),
            eligibility=c.get("eligibility"),
            degree_conditions=c.get("degree_conditions"),
            quota_evidence=c.get("quota_evidence"),
            degrees_evidence=c.get("degrees_evidence"),
            issues=flagged.get(c["name"], []),
        )
        for c in extracted.get("categories", [])
    ]
    cycles = [
        CycleOut(
            description=describe_cycle(c),
            intake=c.intake,
            label=c.label,
            opens_at=c.opens_at,
            closes_at=c.closes_at,
            timezone=c.timezone,
            timezone_assumed=c.timezone_assumed,
            status=c.status,
            estimated=c.estimated,
            nationality_scope=c.nationality_scope,
            nationalities=country_list(c.nationalities),
            funding=c.funding,
            evidence=c.evidence,
            verification=c.verification,
        )
        for c in sorted(row.cycles, key=lambda c: c.closes_at)
    ]
    # 類別 id → 名稱（文件清單只存類別 id）；查詢結果有 keys()，不能直接交給 dict()
    names = {
        category_id: name
        for category_id, name in session.execute(
            select(ScholarshipCategory.id, ScholarshipCategory.name).where(
                ScholarshipCategory.scholarship_id == row.id
            )
        )
    }
    requirements = [
        RequirementOut(
            doc_type=r.doc_type,
            details=r.details,
            required=r.required,
            count=r.count,
            category=names.get(r.category_id) if r.category_id else None,
            evidence=r.evidence,
        )
        for r in session.scalars(select(Requirement).where(Requirement.scholarship_id == row.id).order_by(Requirement.id))
    ]
    scores = [
        ScoreOut(
            category=m.category_name,
            total=m.total,
            cap=m.cap,
            checks=m.checks,
            sub_scores=m.sub_scores,
            unclear=list(m.unclear),
            failed=list(m.failed),
            computed_at=m.computed_at,
        )
        for m in session.scalars(
            select(Match)
            .where(Match.user_id == CURRENT_USER_ID, Match.scholarship_id == row.id)
            .order_by(Match.total.desc())
        )
    ]
    today = datetime.now(TAIPEI).date()
    changes: list[ChangeOut] = []
    for change in session.scalars(
        select(Change)
        .where(Change.scholarship_id == row.id, Change.field.in_(NOTIFIED_FIELDS))
        .order_by(Change.changed_at.desc())
    ):
        # 和通知用同一套規則決定值不值得列出（ADR-064、065）
        text = describe_change(change.field, change.old_value, change.new_value, today=today)
        if text is not None:
            changes.append(ChangeOut(changed_at=change.changed_at, text=text))
    return ScholarshipDetail(
        id=row.id,
        name=row.name,
        name_zh=row.name_zh,
        provider=row.provider,
        countries=country_list(row.countries),
        degrees=list(row.degrees),
        fields=list(row.fields),
        coverage=row.coverage,
        amount=row.amount,
        language_requirements=row.language_requirements,
        other_eligibility=row.other_eligibility,
        requires_admission=row.requires_admission,
        nationality_scope=row.nationality_scope,
        nationalities=country_list(row.nationalities),
        nationality_conditions=row.nationality_conditions,
        nationality_evidence=extracted.get("nationality_evidence"),
        nationality_check=verification.get("nationality"),
        degrees_evidence=extracted.get("degrees_evidence"),
        degrees_check=verification.get("degrees"),
        official_url=row.official_url,
        status=row.status.value,
        stale=stale_of(row, today),
        last_verified_at=row.last_verified_at,
        categories=categories,
        cycles=cycles,
        requirements=requirements,
        scores=scores,
        changes=changes,
    )
