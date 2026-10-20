"""個人資料 API（第 6 天）：網頁的個人資料頁（第 9 天）會呼叫這兩個端點。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.features.profiles.service import (
    CURRENT_USER_ID,
    ProfileIn,
    ProfileOut,
    get_profile,
    save_profile,
    to_out,
)
from app.shared.db import get_session

# FastAPI 的依賴注入：每個請求自動拿到一個資料庫 Session（Annotated 是目前建議的寫法）
DbSession = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/api/profile", tags=["個人資料"])


@router.get("")
def read_profile(session: DbSession) -> ProfileOut:
    row = get_profile(session, CURRENT_USER_ID)
    if row is None:
        raise HTTPException(status_code=404, detail="還沒有個人資料")
    return to_out(row)


@router.put("")
def write_profile(data: ProfileIn, session: DbSession) -> ProfileOut:
    row = save_profile(session, CURRENT_USER_ID, data)
    session.commit()
    return to_out(row)
