"""Gemini 轉接頭的工具呼叫（ADR-082）：不連網，用假的 LangChain 物件代替 Gemini。"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import SecretStr

from app.core.llm.base import ChatMessage, ToolCall, ToolSpec
from app.core.llm.gemini import INPUT_PRICE_PER_M, OUTPUT_PRICE_PER_M, GeminiLLM


class FakeToolChat:
    """假的 ChatGoogleGenerativeAI：記下收到的工具與訊息，回覆一個要呼叫 search 的訊息。"""

    def __init__(self) -> None:
        self.tools: list[dict[str, Any]] = []
        self.sent: list[Any] = []

    def bind_tools(self, tools: list[dict[str, Any]]) -> "FakeToolChat":
        self.tools = tools
        return self

    def invoke(self, messages: list[Any]) -> AIMessage:
        self.sent = messages
        return AIMessage(
            content="",
            tool_calls=[{"name": "search", "args": {"query": "UK scholarship"}, "id": "call-1"}],
            usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
        )


class Prompts:
    """假的用量回呼：只記下 after_call 收到的提示詞。"""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def before_call(self) -> None:
        pass

    def after_call(self, prompt: str, model: str, i: int, o: int, cost: float, error: str | None) -> None:
        self.prompts.append(prompt)


SEARCH = ToolSpec("search", "搜尋網頁", {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})


def make(chat: FakeToolChat, hook: Prompts) -> GeminiLLM:
    llm = GeminiLLM("gemini-test", SecretStr("fake-key"), requests_per_minute=10_000, hook=hook)
    llm._chat = chat  # type: ignore[assignment]
    return llm


def test_step_returns_tool_calls_tokens_and_the_raw_message() -> None:
    chat, hook = FakeToolChat(), Prompts()
    turn = make(chat, hook).step([ChatMessage("system", "任務說明"), ChatMessage("user", "開始")], [SEARCH])
    assert turn.message.role == "assistant"
    assert turn.message.tool_calls == [ToolCall("call-1", "search", {"query": "UK scholarship"})]
    assert (turn.input_tokens, turn.output_tokens) == (50, 10)
    assert turn.cost_usd == (50 * INPUT_PRICE_PER_M + 10 * OUTPUT_PRICE_PER_M) / 1_000_000
    assert isinstance(turn.message.raw, AIMessage)  # 下一輪要原封不動送回
    # 工具照 Gemini 函式宣告的格式交出去
    assert chat.tools == [{"name": "search", "description": "搜尋網頁", "parameters": SEARCH.parameters}]
    # 費用紀錄用任務說明（系統訊息）認出是哪個提示詞
    assert hook.prompts == ["任務說明"]


def test_step_converts_the_whole_conversation() -> None:
    chat = FakeToolChat()
    previous = AIMessage(content="", tool_calls=[{"name": "search", "args": {"query": "q"}, "id": "call-0"}])
    conversation = [
        ChatMessage("system", "任務說明"),
        ChatMessage("user", "開始"),
        ChatMessage("assistant", "", [ToolCall("call-0", "search", {"query": "q"})], raw=previous),
        ChatMessage("tool", "1. 結果", tool_call_id="call-0", name="search"),
    ]
    make(chat, Prompts()).step(conversation, [SEARCH])
    assert len(chat.sent) == 4
    system, user, assistant, tool = chat.sent
    assert isinstance(system, SystemMessage) and system.content == "任務說明"
    assert isinstance(user, HumanMessage) and user.content == "開始"
    assert assistant is previous  # 原始訊息原封不動送回
    assert isinstance(tool, ToolMessage)
    assert (tool.content, tool.tool_call_id, tool.name) == ("1. 結果", "call-0", "search")
