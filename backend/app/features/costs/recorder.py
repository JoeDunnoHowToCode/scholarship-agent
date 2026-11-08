"""用量回呼的實作（ADR-089）：每次 AI 呼叫前檢查每月上限，呼叫後記一筆。"""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.features.costs.log import month_total_usd, record_call
from app.features.costs.usage import NTD_PER_USD, over_cap
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
        agent_run_id: int | None = None,
        sessions: Callable[[], Session] = SessionLocal,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.cap_ntd = cap_ntd
        self.source_id = source_id
        self.run_id = run_id
        self.agent_run_id = agent_run_id
        self._sessions = sessions
        self._clock = clock

    def before_call(self) -> None:
        # 每次都查資料庫的總額，不另外快取：別的程序（worker、指令）花的錢也要算進來
        with self._sessions() as session:
            spent = month_total_usd(session, self._clock())
        if over_cap(spent, self.cap_ntd):
            raise MonthlyCapError(
                f"本月 AI 已花約 NT${spent * NTD_PER_USD:,.0f}，達到每月上限 NT${self.cap_ntd:,.0f}"
            )

    def after_call(
        self, prompt: str, model: str, input_tokens: int, output_tokens: int, cost_usd: float, error: str | None
    ) -> None:
        with self._sessions() as session:
            record_call(
                session, prompt, model, input_tokens, output_tokens, cost_usd, error,
                self.source_id, self.run_id, self.agent_run_id,
            )
            session.commit()
