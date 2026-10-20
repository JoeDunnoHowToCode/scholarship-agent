"""評分結果 API（第 6 天）：網頁的列表（第 9 天）會呼叫這個端點。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.matching.models import Match
from app.features.profiles.service import CURRENT_USER_ID
from app.features.scholarships.models import Scholarship
from app.shared.db import get_session

# FastAPI 的依賴注入：每個請求自動拿到一個資料庫 Session（Annotated 是目前建議的寫法）
DbSession = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/api/matches", tags=["評分"])


class MatchOut(BaseModel):
    """一筆評分；資料表物件不直接回傳（CLAUDE.md）。"""

    scholarship_id: int
    name: str
    category: str
    total: float
    cap: int | None
    unclear: list[str]
    failed: list[str]
    checks: dict[str, Any]
    sub_scores: dict[str, Any]
    official_url: str | None


@router.get("")
def list_matches(session: DbSession, limit: int = 50) -> list[MatchOut]:
    rows = session.execute(
        select(Match, Scholarship)
        .join(Scholarship, Scholarship.id == Match.scholarship_id)
        .where(Match.user_id == CURRENT_USER_ID)
        .order_by(Match.total.desc())
        .limit(limit)
    ).all()
    return [
        MatchOut(
            scholarship_id=row.id,
            name=row.name,
            category=match.category_name,
            total=match.total,
            cap=match.cap,
            unclear=list(match.unclear),
            failed=list(match.failed),
            checks=match.checks,
            sub_scores=match.sub_scores,
            official_url=row.official_url,
        )
        for match, row in rows
    ]
