"""通知歷史 API（第 9 天，ADR-062）：網頁的通知歷史頁呼叫這個端點，只讀。

基準線（第一次啟用時記下、沒有送出的）不列：那些不是你收到過的通知。
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.notifications.models import Event
from app.features.profiles.service import CURRENT_USER_ID
from app.shared.db import get_session

DbSession = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/api/events", tags=["通知"])


class EventOut(BaseModel):
    id: int
    kind: str  # new_scholarship、new_cycle、deadline、change、system
    title: str
    lines: list[str]
    url: str | None
    status: str  # pending 待送、sent 已送、failed 失敗
    created_at: datetime
    sent_at: datetime | None


@router.get("")
def list_events(session: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[EventOut]:
    rows = session.scalars(
        select(Event)
        .where(Event.user_id == CURRENT_USER_ID, Event.status != "baseline")
        .order_by(Event.created_at.desc(), Event.id.desc())
        .limit(limit)
    )
    return [
        EventOut(
            id=e.id,
            kind=e.kind,
            title=e.payload["title"],
            lines=e.payload["lines"],
            url=e.payload["url"],
            status=e.status,
            created_at=e.created_at,
            sent_at=e.sent_at,
        )
        for e in rows
    ]
