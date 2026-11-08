"""agent 迴圈（ADR-082）：用照劇本回覆的假 AI 測停止條件與錯誤處理，不連網。"""

from typing import Any

from app.core.llm.base import ChatMessage, ToolCall, ToolSpec, Turn
from app.features.discovery.agent import StopAgent, Tool, run_agent


def call(name: str, **args: Any) -> Turn:
    """AI 要呼叫一個工具的回覆（每次 0.1 美元，方便測費用上限）。"""
    return Turn(ChatMessage("assistant", "", [ToolCall(f"id-{name}", name, args)]), 10, 2, 0.1)


def answer(text: str) -> Turn:
    """AI 不再呼叫工具、直接回答：代表完成。"""
    return Turn(ChatMessage("assistant", text), 10, 2, 0.1)


class ScriptedLLM:
    """照劇本一個一個回覆；記下每一步收到的對話。劇本用完就一直呼叫 echo。"""

    def __init__(self, turns: list[Turn]) -> None:
        self.turns = turns
        self.seen: list[list[ChatMessage]] = []

    def step(self, messages: list[ChatMessage], tools: list[ToolSpec]) -> Turn:
        self.seen.append(list(messages))
        return self.turns.pop(0) if self.turns else call("echo", text="again")


class Log:
    def __init__(self) -> None:
        self.entries: list[tuple[str, int, str]] = []

    def model(self, number: int, turn: Turn) -> None:
        self.entries.append(("model", number, turn.message.content))

    def tool(self, number: int, name: str, args: dict[str, Any], result: str) -> None:
        self.entries.append(("tool", number, f"{name}:{result}"))


def echo_tool() -> Tool:
    spec = ToolSpec("echo", "回傳同樣的文字", {"type": "object", "properties": {"text": {"type": "string"}}})
    return Tool(spec, lambda args: f"echo {args['text']}")


def failing_tool() -> Tool:
    def run(args: dict[str, Any]) -> str:
        raise ConnectionError("網站連不上")

    return Tool(ToolSpec("fetch", "抓網頁", {"type": "object", "properties": {}}), run)


def run(llm: ScriptedLLM, tools: list[Tool], log: Log | None = None, max_steps: int = 10, max_cost: float = 5.0) -> Any:
    return run_agent(llm, "任務說明", "開始", tools, log or Log(), max_steps, max_cost)


def test_runs_tools_and_stops_when_the_ai_answers() -> None:
    llm, log = ScriptedLLM([call("echo", text="hi"), answer("找到了")]), Log()
    outcome = run(llm, [echo_tool()], log)
    assert (outcome.result, outcome.steps, outcome.final_text) == ("done", 2, "找到了")
    assert outcome.cost_usd == 0.2
    # 第二步時，AI 看得到第一步的工具結果
    second = llm.seen[1]
    assert [m.role for m in second] == ["system", "user", "assistant", "tool"]
    assert (second[3].content, second[3].tool_call_id, second[3].name) == ("echo hi", "id-echo", "echo")
    assert log.entries == [("model", 1, ""), ("tool", 1, "echo:echo hi"), ("model", 2, "找到了")]


def test_stops_at_the_step_limit() -> None:
    outcome = run(ScriptedLLM([]), [echo_tool()], max_steps=3)  # 劇本空的：一直呼叫工具
    assert (outcome.result, outcome.steps) == ("step_limit", 3)


def test_stops_at_the_cost_limit() -> None:
    outcome = run(ScriptedLLM([]), [echo_tool()], max_cost=0.25)  # 每步 0.1：第 3 步後達到
    assert (outcome.result, outcome.steps) == ("cost_limit", 3)


def test_unknown_tools_and_tool_errors_go_back_to_the_ai() -> None:
    llm = ScriptedLLM([call("nope"), call("fetch"), answer("放棄")])
    outcome = run(llm, [echo_tool(), failing_tool()])
    assert outcome.result == "done"
    assert len(llm.seen) == 3
    unknown, failed = llm.seen[1][-1].content, llm.seen[2][-1].content
    assert "沒有這個工具：nope" in unknown and "echo" in unknown  # 告訴 AI 有哪些工具可以用
    assert "工具出錯" in failed and "ConnectionError" in failed


def test_a_tool_can_stop_the_whole_run() -> None:
    def quota(args: dict[str, Any]) -> str:
        raise StopAgent("Tavily 本月額度用完")

    tool = Tool(ToolSpec("search", "搜尋", {"type": "object", "properties": {}}), quota)
    outcome = run(ScriptedLLM([call("search")]), [tool])
    assert (outcome.result, outcome.steps, outcome.final_text) == ("stopped", 1, "Tavily 本月額度用完")
