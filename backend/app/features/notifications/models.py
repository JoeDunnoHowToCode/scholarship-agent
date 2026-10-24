"""events 資料表（ADR-062，spec 資料模型）：要通知的事先記在這裡（Outbox），送出後再標記已送。"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

# 外鍵指向 scholarships：先載入它的資料表定義，只用到這個檔案的指令才不會找不到表
from app.features.scholarships import models as _scholarship_models  # noqa: F401
from app.shared.db import Base


class Event(Base):
    """一件要通知的事。去重鍵在同一位使用者內唯一：重跑產生事件時，已經有的就不會再產生。"""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("user_id", "dedup_key"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)  # ADR-021，第一版固定是 1
    # new_scholarship 新獎學金、new_cycle 新年度開放、deadline 截止提醒、change 資料變更、system 系統
    kind: Mapped[str] = mapped_column(String(32))
    scholarship_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("scholarships.id", ondelete="CASCADE")
    )
    dedup_key: Mapped[str] = mapped_column(Text)  # 例如 deadline:42:2027-01-15:7
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)  # 結構化通知：kind、title、lines、url
    # pending 待送、sent 已送、baseline 第一次啟用時的基準線（不送）、failed 送不出去（例如格式錯）
    status: Mapped[str] = mapped_column(String(16), server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
