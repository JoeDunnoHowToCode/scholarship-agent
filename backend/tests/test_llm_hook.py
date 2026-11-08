"""Gemini 轉接頭在每次呼叫前後叫用量回呼（ADR-089）：不連網，用假的 LangChain 物件代替 Gemini。"""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, SecretStr

from app.core.llm.gemini import (
    INPUT_PRICE_PER_M,
    OUTPUT_PRICE_PER_M,
    GeminiLLM,
    LLMError,
)


class Answer(BaseModel):
    value: str


class Recorder:
    """假的用量回呼：記下被叫了什麼；block=True 時在呼叫前丟錯誤。"""

    def __init__(self, block: bool = False) -> None:
        self.block = block
        self.calls: list[dict[str, Any]] = []

    def before_call(self) -> None:
        if self.block:
            raise RuntimeError("本月已達上限")

    def after_call(
        self, prompt: str, model: str, input_tokens: int, output_tokens: int, cost_usd: float, error: str | None
    ) -> None:
        self.calls.append(
            {"prompt": prompt, "model": model, "in": input_tokens, "out": output_tokens, "cost": cost_usd, "error": error}
        )


class FakeChat:
    """假的 ChatGoogleGenerativeAI：回傳固定的 tokens；fail=True 時呼叫失敗。"""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.invoked = 0

    def with_structured_output(self, schema: type[BaseModel], include_raw: bool) -> "FakeChat":
        return self

    def invoke(self, _input: Any) -> Any:
        self.invoked += 1
        if self.fail:
            raise TimeoutError("連線逾時")
        raw = SimpleNamespace(usage_metadata={"input_tokens": 100, "output_tokens": 20}, text="轉錄稿")
        if isinstance(_input, list):  # read_pdf 傳的是訊息清單，回傳訊息本身
            return raw
        return {"raw": raw, "parsed": Answer(value="ok"), "parsing_error": None}


def make(hook: Recorder, chat: FakeChat) -> GeminiLLM:
    llm = GeminiLLM("gemini-test", SecretStr("fake-key"), requests_per_minute=10_000, hook=hook)
    llm._chat = chat  # type: ignore[assignment]
    return llm


def test_after_call_gets_prompt_tokens_and_cost() -> None:
    hook = Recorder()
    make(hook, FakeChat()).extract("問題", Answer)
    cost = (100 * INPUT_PRICE_PER_M + 20 * OUTPUT_PRICE_PER_M) / 1_000_000
    assert hook.calls == [{"prompt": "問題", "model": "gemini-test", "in": 100, "out": 20, "cost": cost, "error": None}]


def test_before_call_can_stop_the_call() -> None:
    chat = FakeChat()
    with pytest.raises(RuntimeError, match="上限"):
        make(Recorder(block=True), chat).extract("問題", Answer)
    assert chat.invoked == 0  # 擋下來就不送給 Gemini，不花錢


def test_failed_call_is_recorded_with_its_error_kind() -> None:
    hook = Recorder()
    with pytest.raises(LLMError):
        make(hook, FakeChat(fail=True)).extract("問題", Answer)
    assert [(c["in"], c["out"], c["error"]) for c in hook.calls] == [(0, 0, "TimeoutError")]


def test_pdf_reading_is_recorded_too() -> None:
    hook = Recorder()
    make(hook, FakeChat()).read_pdf("轉錄", b"%PDF")
    assert [(c["prompt"], c["in"], c["error"]) for c in hook.calls] == [("轉錄", 100, None)]
