"""profiles 資料表（ADR-021、055）：每個使用者一份個人資料，第一版只有 user_id = 1。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class Profile(Base):
    """評分用的個人資料。ADR-055：不收成績、語言檢定、工作年資、年齡。"""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)  # ADR-021：第一版固定 1
    nationality: Mapped[str] = mapped_column(String(2))  # ISO 國碼（ADR-054），例如 TW
    target_degree: Mapped[str] = mapped_column(String(16))  # bachelor／master／phd
    current_major: Mapped[str | None] = mapped_column(Text)  # 選填：目前科系
    target_fields: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")  # 選填
    target_countries: Mapped[list[str]] = mapped_column(ARRAY(String(2)), server_default="{}")
    # 每次修改加一；評分時記下用的是哪一版
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
