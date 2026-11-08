"""紀錄頁的 API（第 10 天段 6，ADR-089）：本月費用、依功能分、最近 7 天、agent 的執行與每一步。"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.shared.db import get_session

DbSession = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/api", tags=["紀錄"])


class FeatureCost(BaseModel):
    feature: str
    calls: int
    ntd: float


class DayCost(BaseModel):
    day: date
    ntd: float


class CostsOut(BaseModel):
    month_ntd: float
    cap_ntd: float
    by_feature: list[FeatureCost]
    by_day: list[DayCost]


class AgentRunOut(BaseModel):
    id: int
    task: str
    target: str | None
    started_at: datetime
    result: str | None
    steps: int
    ntd: float
    final_text: str | None


class AgentStepOut(BaseModel):
    number: int
    kind: str
    tool: str | None
    args: dict[str, object] | None
    summary: str
    full_text: str | None  # 30 天後是空的（ADR-089）
    input_tokens: int
    output_tokens: int


@router.get("/costs")
def read_costs(session: DbSession) -> CostsOut:
    return CostsOut(month_ntd=0, cap_ntd=0, by_feature=[], by_day=[])  # 骨架


@router.get("/agent-runs")
def list_agent_runs(session: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 30) -> list[AgentRunOut]:
    return []  # 骨架


@router.get("/agent-runs/{run_id}/steps")
def list_agent_steps(run_id: int, session: DbSession) -> list[AgentStepOut]:
    return []  # 骨架
