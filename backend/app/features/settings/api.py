"""設定頁的 API（第 10 天段 6）：通知門檻、每月上限、斷路器、agent 加的來源。"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.features.settings.service import CAP_LIMIT_NTD
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


@router.get("/settings")
def read_settings(session: DbSession) -> SettingsOut:
    return SettingsOut(notify_threshold=0, monthly_cap_ntd=0, cap_limit_ntd=CAP_LIMIT_NTD,
                       breaker=BreakerOut(open=False, reason=None, opened_at=None))  # 骨架


@router.put("/settings")
def update_settings(body: SettingsIn, session: DbSession) -> SettingsOut:
    return read_settings(session)  # 骨架


@router.post("/settings/breaker/reset")
def reset_breaker(session: DbSession) -> SettingsOut:
    return read_settings(session)  # 骨架


@router.get("/discovery/sources")
def list_agent_sources(session: DbSession) -> list[AgentSourceOut]:
    return []  # 骨架


@router.patch("/discovery/sources/{source_id}")
def toggle_source(source_id: int, body: SourceToggle, session: DbSession) -> AgentSourceOut | None:
    return None  # 骨架
