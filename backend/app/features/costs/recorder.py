"""用量回呼的實作（ADR-089）：每次 AI 呼叫前檢查每月上限，呼叫後記一筆。"""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.features.pipeline.errors import CostLimitError
from app.shared.db import SessionLocal


class MonthlyCapError(CostLimitError):
    """本月 AI 費用已達每月上限（ADR-013、049）。是 CostLimitError 的一種，背景工作遇到會打開斷路器。"""


class CostRecorder:
    """符合 core/llm 的 UsageHook。每次用自己的資料庫連線並馬上 commit：呼叫的工作之後失敗、復原，紀錄也不會不見。"""

    def __init__(
        self,
        cap_ntd: float,
        source_id: int | None = None,
        run_id: int | None = None,
        sessions: Callable[[], Session] = SessionLocal,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.cap_ntd = cap_ntd
        self.source_id = source_id
        self.run_id = run_id
        self._sessions = sessions
        self._clock = clock

    def before_call(self) -> None:
        pass  # 骨架

    def after_call(
        self, prompt: str, model: str, input_tokens: int, output_tokens: int, cost_usd: float, error: str | None
    ) -> None:
        pass  # 骨架
