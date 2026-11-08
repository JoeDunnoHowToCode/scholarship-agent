"""讀寫設定（第 10 天段 6）：資料庫有值就用，沒有就用 .env 的預設值。"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.settings.models import AppSetting
from app.shared.settings import settings

CAP_LIMIT_NTD = 7000.0  # ADR-049：設定頁只能調低，不能超過


@dataclass(frozen=True)
class Effective:
    notify_threshold: int
    monthly_cap_ntd: float


def effective(session: Session, user_id: int) -> Effective:
    """現在生效的設定。"""
    row = session.scalars(select(AppSetting).where(AppSetting.user_id == user_id)).first()
    threshold = row.notify_threshold if row and row.notify_threshold is not None else settings.notify_threshold
    cap = row.monthly_cap_ntd if row and row.monthly_cap_ntd is not None else settings.monthly_cap_ntd
    return Effective(threshold, min(cap, CAP_LIMIT_NTD))  # .env 寫錯也不會超過 ADR-049 的上限


def save(session: Session, user_id: int, notify_threshold: int, monthly_cap_ntd: float) -> None:
    """存設定；範圍檢查由 API 的 Pydantic 模型負責。呼叫的人負責 commit。"""
    row = session.scalars(select(AppSetting).where(AppSetting.user_id == user_id)).first()
    if row is None:
        row = AppSetting(user_id=user_id)
        session.add(row)
    row.notify_threshold, row.monthly_cap_ntd = notify_threshold, monthly_cap_ntd
    session.flush()
