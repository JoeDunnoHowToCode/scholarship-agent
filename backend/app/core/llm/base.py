"""模型插座（ADR-005）：功能程式只依賴這個介面，不直接依賴某一家模型。

之後要換模型或加本地模型（ADR-009），只要在 core/llm 加一個符合這個介面的轉接頭。
"""

from typing import Protocol

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
