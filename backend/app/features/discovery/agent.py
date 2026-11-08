"""agent 迴圈（ADR-082）：AI 決定呼叫哪個工具 → 程式執行 → 結果交回 AI → 直到 AI 說完成或碰到上限。

迴圈是我們自己寫的（不用框架），每一步交給 StepLog 記錄（ADR-086、089）。
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.core.llm.base import ToolCallingLLM, ToolSpec, Turn


class StopAgent(Exception):
    """工具要求整次執行馬上結束（例如 Tavily 本月額度用完）；訊息會記成結果。"""


@dataclass
class Tool:
    spec: ToolSpec  # 給 AI 看的說明
    run: Callable[[dict[str, Any]], str]  # 執行，回傳交給 AI 的文字


Result = Literal["done", "step_limit", "cost_limit", "stopped"]


@dataclass
class Outcome:
    result: Result
    steps: int  # 呼叫了幾次 AI
    cost_usd: float
    final_text: str  # AI 最後說的話，或停下來的原因


class StepLog(Protocol):
    """每一步的紀錄（寫資料庫的實作在 trace.py）。"""

    def model(self, number: int, turn: Turn) -> None: ...

    def tool(self, number: int, name: str, args: dict[str, Any], result: str) -> None: ...


def run_agent(
    llm: ToolCallingLLM,
    system: str,
    task: str,
    tools: list[Tool],
    log: StepLog,
    max_steps: int,
    max_cost_usd: float,
) -> Outcome:
    return Outcome("done", 0, 0.0, "")  # 骨架
