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
