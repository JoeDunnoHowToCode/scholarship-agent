"""agent 的執行紀錄（ADR-086、089）。"""

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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class AgentRun(Base):
    """每次 agent 執行一筆：做什麼任務、結果、幾步、花多少。"""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    task: Mapped[str] = mapped_column(String(32))  # universities、search、new_url、smoke
    target: Mapped[str | None] = mapped_column(String(256))  # 例如 university:12、source:45
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(String(16))  # done、step_limit、cost_limit、stopped、error
    steps: Mapped[int] = mapped_column(Integer, server_default="0")
    cost_usd: Mapped[float] = mapped_column(Float, server_default="0")
    final_text: Mapped[str | None] = mapped_column(Text)  # AI 最後說的話，或停下來的原因


class AgentStep(Base):
    """agent 的每一步：AI 的回覆或一次工具呼叫。全文保留 30 天，其他欄位永久保留（ADR-089）。"""

    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    agent_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(AgentRun.id, ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)  # 第幾次呼叫 AI；工具呼叫跟著它所屬的那一步
    kind: Mapped[str] = mapped_column(String(8))  # model 或 tool
    tool: Mapped[str | None] = mapped_column(String(64))
    args: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # 工具的參數，例如搜尋字、網址
    summary: Mapped[str] = mapped_column(Text)  # 一句話摘要（前 200 字）
    full_text: Mapped[str | None] = mapped_column(Text)  # AI 完整回覆或工具結果；30 天後清成空白
    input_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class University(Base):
    """逐校找的學校名單（ADR-083）：從各國官方名單建立的種子（universities.csv）。"""

    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    country: Mapped[str] = mapped_column(String(2))  # ISO 國碼，例如 GB、SE
    region: Mapped[str | None] = mapped_column(String(32))  # 英國的 England／Scotland／Wales／Northern Ireland
    name: Mapped[str] = mapped_column(Text)
    homepage: Mapped[str] = mapped_column(Text, unique=True)  # agent 從這裡出發
    source_url: Mapped[str] = mapped_column(Text)  # 名單出處（官方網址）
    note: Mapped[str | None] = mapped_column(Text)  # 例如冰島的「首頁由人工確認」
    last_searched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 上次逐校找的時間
    last_result: Mapped[str | None] = mapped_column(String(32))  # 上次的結果，例如 done、step_limit
