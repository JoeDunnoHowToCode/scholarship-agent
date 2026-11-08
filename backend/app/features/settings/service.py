"""讀寫設定（第 10 天段 6）：資料庫有值就用，沒有就用 .env 的預設值。"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.shared.settings import settings

CAP_LIMIT_NTD = 7000.0  # ADR-049：設定頁只能調低，不能超過


@dataclass(frozen=True)
class Effective:
    notify_threshold: int
    monthly_cap_ntd: float


def effective(session: Session, user_id: int) -> Effective:
    """現在生效的設定。"""
    return Effective(settings.notify_threshold, settings.monthly_cap_ntd)  # 骨架


def save(session: Session, user_id: int, notify_threshold: int, monthly_cap_ntd: float) -> None:
    """存設定；範圍檢查由 API 的 Pydantic 模型負責。呼叫的人負責 commit。"""
    # 骨架
