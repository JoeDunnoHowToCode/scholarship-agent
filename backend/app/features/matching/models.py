"""matches 資料表（spec 資料模型、ADR-055）：每個使用者對每個（獎學金 × 類別）的評分。"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

# 外鍵指向 scholarships：先載入它的資料表定義，只用到這個檔案的指令才不會找不到表
from app.features.scholarships import models as _scholarship_models  # noqa: F401
from app.shared.db import Base


class Match(Base):
    """一筆評分。用「獎學金＋類別名稱」對應，不直接指向類別表：
    重抽會整批重寫類別表，直接指向的話，評分會跟著被刪掉，又要花錢重算。"""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("user_id", "scholarship_id", "category_name"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)  # ADR-021
    scholarship_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scholarships.id", ondelete="CASCADE")
    )
    category_name: Mapped[str] = mapped_column(Text)
    total: Mapped[float] = mapped_column(Float)  # 0–100，已套用上限
    cap: Mapped[int | None] = mapped_column(Integer)  # 20、80，或沒有上限
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB)  # 國籍、學位、時間：結果與原因
    sub_scores: Mapped[dict[str, Any]] = mapped_column(JSONB)  # 四個分項：分數與理由
    unclear: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")  # 待確認的條件
    failed: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")  # 不符合的條件
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    profile_version: Mapped[int] = mapped_column(Integer)
    # 送給 AI 的內容的雜湊：內容一樣就沿用分項分數，不再呼叫 AI（docs/day-06.md 第 10 點）
    input_hash: Mapped[str | None] = mapped_column(String(64))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
