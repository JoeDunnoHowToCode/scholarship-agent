"""agent 迴圈（ADR-082）：AI 決定呼叫哪個工具 → 程式執行 → 結果交回 AI → 直到 AI 說完成或碰到上限。

迴圈是我們自己寫的（不用框架），每一步交給 StepLog 記錄（ADR-086、089）。
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.core.llm.base import ChatMessage, ToolCall, ToolCallingLLM, ToolSpec, Turn


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
    """跑一次 agent。步數＝呼叫 AI 的次數；每次 AI 回覆後檢查上限，到了就停。"""
    by_name = {tool.spec.name: tool for tool in tools}
    specs = [tool.spec for tool in tools]
    messages = [ChatMessage("system", system), ChatMessage("user", task)]
    steps, cost = 0, 0.0
    while True:
        turn = llm.step(messages, specs)
        steps += 1
        cost += turn.cost_usd
        log.model(steps, turn)
        messages.append(turn.message)
        if not turn.message.tool_calls:
            return Outcome("done", steps, cost, turn.message.content)  # AI 不再呼叫工具：它認為做完了
        for call in turn.message.tool_calls:
            try:
                result = _run_tool(by_name, call)
            except StopAgent as stop:
                log.tool(steps, call.name, call.args, f"停止：{stop}")
                return Outcome("stopped", steps, cost, str(stop))
            log.tool(steps, call.name, call.args, result)
            messages.append(ChatMessage("tool", result, tool_call_id=call.id, name=call.name))
        if cost >= max_cost_usd:
            return Outcome("cost_limit", steps, cost, f"這次執行已花 US${cost:.3f}，達到上限")
        if steps >= max_steps:
            return Outcome("step_limit", steps, cost, f"已經 {steps} 步，達到上限")


def _run_tool(by_name: dict[str, Tool], call: ToolCall) -> str:
    """執行一次工具。AI 叫錯工具或工具出錯，都變成文字交回 AI，讓它自己決定下一步，不讓程式當掉。"""
    tool = by_name.get(call.name)
    if tool is None:
        return f"沒有這個工具：{call.name}。可以用的工具：{', '.join(by_name)}"
    try:
        return tool.run(call.args)
    except StopAgent:
        raise
    # 故意接住所有錯誤：網站連不上、參數格式錯（KeyError）等，都交給 AI 判斷要換做法還是放棄
    except Exception as error:  # noqa: BLE001
        return f"工具出錯：{type(error).__name__}: {error}"
