"""把 agent 的每一步寫進資料庫（ADR-089），以及清掉超過 30 天的全文。

用法：uv run python -m app.features.discovery.trace <agent_run_id>   照順序印出某次執行的每一步
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.llm.base import Turn
from app.shared.db import SessionLocal

KEEP_FULL_TEXT = timedelta(days=30)  # ADR-089
SUMMARY_CHARS = 200  # 「Claude 自行決定」第 8 點


class DbStepLog:
    """符合 agent.StepLog。每一步用自己的連線馬上 commit：執行到一半當掉，前面的步驟也還在。"""

    def __init__(self, agent_run_id: int, sessions: Callable[[], Session] = SessionLocal) -> None:
        self.agent_run_id = agent_run_id
        self._sessions = sessions

    def model(self, number: int, turn: Turn) -> None:
        pass  # 骨架

    def tool(self, number: int, name: str, args: dict[str, Any], result: str) -> None:
        pass  # 骨架


def clear_old_texts(session: Session, now: datetime) -> int:
    """把超過 30 天的全文清成空白，回傳清了幾筆；摘要、參數、tokens 保留。呼叫的人負責 commit。"""
    return 0  # 骨架
