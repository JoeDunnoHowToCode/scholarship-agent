"""背景工作的資料表（第 7 天，ADR-056、057）：斷路器，以及每天的檢查紀錄。"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Identity, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class Breaker(Base):
    """斷路器（ADR-056）：打開時所有 AI 步驟都跳過，等使用者處理好、用指令恢復。"""

    __tablename__ = "breakers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)  # 目前只有 ai 一個
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 空白代表關著
    reason: Mapped[str | None] = mapped_column(Text)


class Run(Base):
    """每天的檢查一筆（ADR-057）：用台灣的日期判斷今天開始過沒，一天只開始一次。"""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, unique=True)  # 台灣的日期
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 放了幾件工作、收尾時各步驟的結果
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
