"""跑一次 agent 並留下紀錄（ADR-082、086、089）：建立執行紀錄 → 跑迴圈 → 寫結果。

用法：uv run python -m app.features.discovery.runner --smoke [--max-cost NT$]   真的跑一次小任務，確認整條路通
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.llm.base import ToolCallingLLM
from app.features.discovery.agent import Outcome
from app.features.discovery.tools import Toolbox
from app.shared.db import SessionLocal


def execute(
    task: str,
    target: str | None,
    system: str,
    task_text: str,
    toolbox: Toolbox,
    with_search: bool,
    max_steps: int,
    max_cost_usd: float,
    make_llm: Callable[[int], ToolCallingLLM],
    sessions: Callable[[], Session] = SessionLocal,
) -> tuple[int, Outcome]:
    """回傳（agent_runs.id, 結果）。出錯時記成 error 再往外丟，讓背景工作照 ADR-056 分類。"""
    return 0, Outcome("done", 0, 0.0, "")  # 骨架
