"""設定頁的 API（第 10 天段 6）：通知門檻、每月上限、斷路器、agent 加的來源。"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.features.pipeline import breaker
from app.features.profiles.service import CURRENT_USER_ID
from app.features.scholarships.models import MAIN_KEY, Scholarship
from app.features.settings.service import CAP_LIMIT_NTD, effective, save
from app.features.sources.models import Discovery, Source, SourceStatus
from app.shared.db import get_session

DbSession = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/api", tags=["設定"])


class BreakerOut(BaseModel):
    open: bool
    reason: str | None
    opened_at: datetime | None


class SettingsOut(BaseModel):
    notify_threshold: int
    monthly_cap_ntd: float
    cap_limit_ntd: float  # 上限的上限（ADR-049）
    breaker: BreakerOut


class SettingsIn(BaseModel):
    notify_threshold: int = Field(ge=0, le=100)
    monthly_cap_ntd: float = Field(ge=1, le=CAP_LIMIT_NTD)


class AgentSourceOut(BaseModel):
    id: int
    name: str
    url: str
    status: str  # candidate 候選、approved 已加入、rejected 已排除
    enabled: bool
    review_note: str | None  # 排除、停用的原因
    created_at: datetime
    decided_at: datetime | None
    scholarships: int  # 這個來源目前抽出幾筆獎學金


class SourceToggle(BaseModel):
    enabled: bool


class ReviewOut(BaseModel):
    """AI 判斷「這頁不是獎學金」、但引用沒核對過的來源（ADR-115），等你決定停用或保留。"""

    source_id: int
    name: str
    url: str
    evidence: str | None  # AI 引用的原文句子
    check: str | None  # 引用的核對結果，例如 not_supported（引用撐不起判斷）、quote_not_found（原文裡找不到）


@router.get("/settings")
def read_settings(session: DbSession) -> SettingsOut:
    current = effective(session, CURRENT_USER_ID)
    row = breaker.get(session)
    is_open = row is not None and row.opened_at is not None
    return SettingsOut(
        notify_threshold=current.notify_threshold,
        monthly_cap_ntd=current.monthly_cap_ntd,
        cap_limit_ntd=CAP_LIMIT_NTD,
        breaker=BreakerOut(
            open=is_open, reason=row.reason if is_open and row else None, opened_at=row.opened_at if row else None
        ),
    )


@router.put("/settings")
def update_settings(body: SettingsIn, session: DbSession) -> SettingsOut:
    save(session, CURRENT_USER_ID, body.notify_threshold, body.monthly_cap_ntd)
    session.commit()
    return read_settings(session)


@router.post("/settings/breaker/reset")
def reset_breaker(session: DbSession) -> SettingsOut:
    """處理好之後恢復 AI 步驟（和指令 breaker --reset 一樣，ADR-056）。"""
    breaker.reset(session)
    session.commit()
    return read_settings(session)


@router.get("/discovery/sources")
def list_agent_sources(session: DbSession) -> list[AgentSourceOut]:
    """agent 加的來源（ADR-078），以及被停用、有寫原因的來源（例如被取代，ADR-095）。新的在前。"""
    counts = (
        select(Scholarship.source_id, func.count().label("n")).group_by(Scholarship.source_id).subquery()
    )
    rows = session.execute(
        select(Source, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.source_id == Source.id)
        .where(or_(Source.discovery == Discovery.SEARCH, Source.disabled_at.is_not(None)))
        .order_by(Source.created_at.desc(), Source.id.desc())
    ).tuples()
    return [_out(source, int(n)) for source, n in rows]


@router.patch("/discovery/sources/{source_id}")
def toggle_source(source_id: int, body: SourceToggle, session: DbSession) -> AgentSourceOut:
    """停用或恢復一個來源。恢復時清掉停用原因與「連續抽不到」的次數，從頭算。"""
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="沒有這個來源")
    if body.enabled:
        source.enabled, source.disabled_at, source.review_note, source.empty_extractions = True, None, None, 0
    else:
        source.enabled, source.disabled_at = False, datetime.now(UTC)
        source.review_note = source.review_note or "在設定頁停用"
    session.commit()
    n = session.scalar(select(func.count()).select_from(Scholarship).where(Scholarship.source_id == source_id))
    return _out(source, int(n or 0))


@router.get("/settings/review")
def list_review(session: DbSession) -> list[ReviewOut]:
    """判斷不是獎學金、但引用沒核對過的來源（ADR-115）：核對過的已經自動停用（ADR-107 A2），不列。"""
    extracted = Scholarship.extracted
    rows = session.execute(
        select(Source, extracted["not_scholarship_evidence"].astext, extracted["verification"]["not_scholarship"].astext)
        .join(Scholarship, Scholarship.source_id == Source.id)
        .where(
            Scholarship.key == MAIN_KEY,  # 「不是獎學金」是整頁的判斷，看主角那筆
            extracted["not_scholarship"].astext == "true",
            func.coalesce(extracted["verification"]["not_scholarship"].astext, "") != "supported",
            Source.status == SourceStatus.APPROVED,
            Source.enabled.is_(True),
            func.coalesce(Source.review_note, "") != KEPT_NOTE,  # 你按過保留的不再列
        )
        .order_by(Source.id)
    ).tuples()
    return [
        ReviewOut(source_id=source.id, name=source.name, url=source.url, evidence=evidence, check=check)
        for source, evidence, check in rows
    ]


class ReviewAction(BaseModel):
    # disable：你確認這頁不是獎學金，停用來源；keep：你判斷 AI 錯了，照常檢查
    action: Literal["disable", "keep"]


DISABLED_NOTE = "你在設定頁停用：這頁不是獎學金"
KEPT_NOTE = "你在設定頁保留：這頁有獎學金"


@router.post("/settings/review/{source_id}")
def decide_review(source_id: int, body: ReviewAction, session: DbSession) -> list[ReviewOut]:
    """你對一個「判斷不是獎學金」的來源做決定（ADR-115）；回傳更新後的清單。
    停用後，它的獎學金在當天收尾的 refresh 封存（總檢查 A6）。"""
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="沒有這個來源")
    if body.action == "keep":
        source.review_note = KEPT_NOTE  # 之後重抽同樣的判斷也不再列出來
    else:
        source.enabled, source.disabled_at, source.review_note = False, datetime.now(UTC), DISABLED_NOTE
    session.commit()
    return list_review(session)


def _out(source: Source, scholarships: int) -> AgentSourceOut:
    return AgentSourceOut(
        id=source.id, name=source.name, url=source.url, status=source.status.value, enabled=source.enabled,
        review_note=source.review_note, created_at=source.created_at, decided_at=source.decided_at,
        scholarships=scholarships,
    )
