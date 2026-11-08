"""紀錄頁的 API（第 10 天段 6，ADR-089）：本月費用、依功能分、最近 7 天、agent 的執行與每一步。"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.costs.summary import summarize
from app.features.costs.usage import NTD_PER_USD
from app.features.discovery.models import AgentRun, AgentStep
from app.features.profiles.service import CURRENT_USER_ID
from app.features.settings.service import effective
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
    summary = summarize(session, datetime.now(UTC))
    return CostsOut(
        month_ntd=summary.month_usd * NTD_PER_USD,
        cap_ntd=effective(session, CURRENT_USER_ID).monthly_cap_ntd,
        by_feature=[FeatureCost(feature=f, calls=n, ntd=usd * NTD_PER_USD) for f, n, usd in summary.by_feature],
        by_day=[DayCost(day=d, ntd=usd * NTD_PER_USD) for d, usd in summary.by_day],
    )


@router.get("/agent-runs")
def list_agent_runs(session: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 30) -> list[AgentRunOut]:
    """最近的 agent 執行，新的在前。"""
    runs = session.scalars(select(AgentRun).order_by(AgentRun.started_at.desc(), AgentRun.id.desc()).limit(limit))
    return [
        AgentRunOut(
            id=r.id, task=r.task, target=r.target, started_at=r.started_at, result=r.result, steps=r.steps,
            ntd=r.cost_usd * NTD_PER_USD, final_text=r.final_text,
        )
        for r in runs
    ]


@router.get("/agent-runs/{run_id}/steps")
def list_agent_steps(run_id: int, session: DbSession) -> list[AgentStepOut]:
    """某次執行的每一步，照順序；超過 30 天的沒有全文，只有摘要（ADR-089）。"""
    steps = session.scalars(select(AgentStep).where(AgentStep.agent_run_id == run_id).order_by(AgentStep.id))
    return [
        AgentStepOut(
            number=s.number, kind=s.kind, tool=s.tool, args=s.args, summary=s.summary, full_text=s.full_text,
            input_tokens=s.input_tokens, output_tokens=s.output_tokens,
        )
        for s in steps
    ]
