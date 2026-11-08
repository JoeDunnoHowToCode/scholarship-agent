"""網頁設定頁可以改的設定（第 10 天段 6）：存在資料庫，沒設定的用 .env 的預設值。"""

from sqlalchemy import BigInteger, Float, Identity, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)  # ADR-021：第一版固定是 1
    notify_threshold: Mapped[int | None] = mapped_column(Integer)  # 通知門檻（適配度 0–100）
    monthly_cap_ntd: Mapped[float | None] = mapped_column(Float)  # 每月 AI 費用上限（新台幣，最多 7,000）
