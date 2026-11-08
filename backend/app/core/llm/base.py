"""模型插座（ADR-005）：功能程式只依賴這個介面，不直接依賴某一家模型。

之後要換模型或加本地模型（ADR-009），只要在 core/llm 加一個符合這個介面的轉接頭。
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel


class StructuredLLM(Protocol):
    def extract[M: BaseModel](self, prompt: str, schema: type[M]) -> M:
        """把 prompt 交給模型，回傳符合 schema 的 Pydantic 物件。"""
        ...


class PdfReader(Protocol):
    def read_pdf(self, prompt: str, pdf: bytes) -> str:
        """把 PDF 原檔連同 prompt 交給模型，回傳模型寫的文字（ADR-037）。"""
        ...


class Embedder(Protocol):
    """把文字變成向量（ADR-050、052）。各家模型要求的前綴寫在轉接頭裡，功能程式不用知道。"""

    model_id: str  # 模型名稱加維度，例如 gemini-embedding-2@1536；換模型就要全部重算

    def embed_documents(self, items: list[tuple[str, str]]) -> list[list[float]]:
        """（標題, 內容）一批變成向量，順序和輸入一樣。"""
        ...

    def embed_query(self, text: str) -> list[float]:
        """使用者的問句變成向量。"""
        ...


class UsageHook(Protocol):
    """每次呼叫 AI 的前後各叫一次（ADR-089）：轉接頭不碰資料庫，記錄與擋上限由功能程式實作。"""

    def before_call(self) -> None:
        """呼叫前；丟例外就不呼叫（例如本月費用已達上限）。"""
        ...

    def after_call(
        self, prompt: str, model: str, input_tokens: int, output_tokens: int, cost_usd: float, error: str | None
    ) -> None:
        """呼叫後（成功或失敗都會叫）；error 是失敗的錯誤種類，成功時是 None。"""
        ...


@dataclass
class ToolSpec:
    """給 AI 看的工具說明（ADR-082）：名稱、什麼時候用、參數的 JSON Schema。"""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    """AI 要求呼叫一次工具。"""

    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ChatMessage:
    """agent 對話裡的一則訊息；功能程式只用這個，不碰 LangChain 的訊息類別。"""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)  # assistant：要呼叫的工具
    tool_call_id: str | None = None  # tool：回覆的是哪一次呼叫
    name: str | None = None  # tool：工具名稱
    raw: Any = None  # assistant：轉接頭的原始訊息，下一輪原封不動送回（Gemini 3 的 thought signature 在裡面）


@dataclass
class Turn:
    """AI 的一次回覆，加上這次用了多少。"""

    message: ChatMessage
    input_tokens: int
    output_tokens: int
    cost_usd: float


class ToolCallingLLM(Protocol):
    def step(self, messages: list[ChatMessage], tools: list[ToolSpec]) -> Turn:
        """把目前的對話和工具清單交給模型，回傳它的下一個回覆（可能是文字，也可能要呼叫工具）。"""
        ...
