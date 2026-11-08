"""費用紀錄的資料表（ADR-086、089）。"""

from datetime import datetime

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
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.db import Base


class LLMCall(Base):
    """每次 AI 呼叫一筆：成功或失敗都記。只存數字與版本，不存提示詞全文（ADR-089）。"""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    feature: Mapped[str] = mapped_column(String(64))  # 提示詞名稱（例如 extract、score）；認不出來是 unknown
    prompt_version: Mapped[str | None] = mapped_column(String(64))  # 例如 extract-12
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)  # 失敗的錯誤種類；成功是空白
    # 是哪個來源、哪一天的檢查花的（指令手動執行時可能都是空白）
    source_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sources.id", ondelete="SET NULL"))
    run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("runs.id", ondelete="SET NULL"))
