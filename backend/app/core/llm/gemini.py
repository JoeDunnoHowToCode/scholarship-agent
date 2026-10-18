"""Gemini 轉接頭（ADR-010、011、015、037）：透過 LangChain 呼叫 Gemini。"""

import base64
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, SecretStr

from app.core.llm.ratelimit import RateLimiter

# Gemini 3.5 Flash-Lite 每百萬 tokens 的價格（美元，Gemini API 定價頁；docs/spec.md 成本粗估）
INPUT_PRICE_PER_M = 0.30
OUTPUT_PRICE_PER_M = 2.50
MAX_RETRIES = 2  # ADR-011：結構化輸出驗證失敗時，把錯誤回饋給模型重試，最多 2 次


class MissingApiKeyError(RuntimeError):
    """沒有設定 Gemini 金鑰。"""


class LLMError(RuntimeError):
    """呼叫模型失敗。功能程式只需要接這一種例外，不必認識 Google 各種錯誤類別。"""


class ExtractionError(LLMError):
    """重試後模型仍然沒有回傳符合 schema 的資料。"""


class GeminiLLM:
    """符合 StructuredLLM 與 PdfReader 插座的 Gemini 實作。"""

    def __init__(
        self, model: str, api_key: SecretStr | None, requests_per_minute: int = 60
    ) -> None:
        if api_key is None or not api_key.get_secret_value():
            raise MissingApiKeyError(
                "沒有 Gemini 金鑰：請在 backend/.env 設定 GOOGLE_API_KEY=你的金鑰"
            )
        # 金鑰明確傳進來：pydantic-settings 讀 .env 時不會放進環境變數，LangChain 自己讀不到
        # 不設定 temperature：Gemini 3 系列官方建議維持預設值
        # 輸出上限調高：PDF 轉錄一批 10 頁、長的抽取結果都可能超過預設值
        # timeout：連線斷掉（例如電腦睡眠）時不會永遠卡住；實測曾卡住整晚
        self._chat = ChatGoogleGenerativeAI(
            model=model, api_key=api_key, max_output_tokens=32_000, timeout=120
        )
        # 這次執行累計用了多少 tokens（ADR-013；完整的成本表是第 10 天）
        self._limiter = RateLimiter(requests_per_minute)  # ADR-042
        self.input_tokens = 0
        self.output_tokens = 0

    def extract[M: BaseModel](self, prompt: str, schema: type[M]) -> M:
        # 預設 method="json_schema"，也就是 Gemini 原生的結構化輸出（ADR-011）
        # include_raw=True：解析失敗時不丟例外，而是把錯誤交給我們決定要不要重試
        runnable = self._chat.with_structured_output(schema, include_raw=True)
        current = prompt
        for _ in range(MAX_RETRIES + 1):
            self._limiter.wait()
            try:
                result: dict[str, Any] = runnable.invoke(current)  # type: ignore[assignment]
            except Exception as failure:
                # 轉接頭的邊界：把 Google 與 LangChain 的各種錯誤統一成 LLMError
                raise LLMError(f"{type(failure).__name__}: {failure}") from failure
            self._count(result["raw"])
            parsed = result["parsed"]
            if isinstance(parsed, schema):
                return parsed
            error = result["parsing_error"] or f"回傳的不是 {schema.__name__}"
            # 把錯誤附在原本的提示詞後面，讓模型知道哪裡不符合 schema
            current = f"{prompt}\n\n上一次的回答不符合格式，錯誤如下，請修正後重新回答：\n{error}"
        raise ExtractionError(f"重試 {MAX_RETRIES} 次仍不符合 {schema.__name__}：{error}")

    def read_pdf(self, prompt: str, pdf: bytes) -> str:
        # Gemini 直接讀 PDF 原檔（看得到表格與版面），用 base64 放進訊息
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "file",
                    "base64": base64.b64encode(pdf).decode(),
                    "mime_type": "application/pdf",
                },
            ]
        )
        self._limiter.wait()
        try:
            response = self._chat.invoke([message])
        except Exception as error:
            raise LLMError(f"{type(error).__name__}: {error}") from error
        self._count(response)
        return response.text

    def cost_usd(self) -> float:
        return (
            self.input_tokens * INPUT_PRICE_PER_M + self.output_tokens * OUTPUT_PRICE_PER_M
        ) / 1_000_000

    def usage_line(self) -> str:
        return (
            f"tokens：輸入 {self.input_tokens:,}、輸出 {self.output_tokens:,}，"
            f"約 US${self.cost_usd():.3f}（NT${self.cost_usd() * 32:.1f}）"
        )

    def _count(self, message: Any) -> None:
        usage = getattr(message, "usage_metadata", None) or {}
        self.input_tokens += usage.get("input_tokens", 0)
        self.output_tokens += usage.get("output_tokens", 0)


class GeminiEmbedder:
    """符合 Embedder 插座的 Gemini 實作（gemini-embedding-2）。

    gemini-embedding-2 不用 task_type 參數，而是在文字前面加前綴（Gemini 官方說明）：
    原文寫成「title: 標題 | text: 內容」，問句寫成「task: search result | query: 問句」。
    """

    BATCH = 100  # 一次送幾段

    def __init__(
        self,
        model: str,
        api_key: SecretStr | None,
        dimensions: int,
        requests_per_minute: int = 60,
    ) -> None:
        if api_key is None or not api_key.get_secret_value():
            raise MissingApiKeyError(
                "沒有 Gemini 金鑰：請在 backend/.env 設定 GOOGLE_API_KEY=你的金鑰"
            )
        self._client = GoogleGenerativeAIEmbeddings(
            model=model, google_api_key=api_key, output_dimensionality=dimensions
        )
        self._limiter = RateLimiter(requests_per_minute)  # ADR-042
        self.model_id = f"{model}@{dimensions}"
        self.characters = 0  # 送出的字數，用來粗估費用

    def embed_documents(self, items: list[tuple[str, str]]) -> list[list[float]]:
        texts = [f"title: {title or 'none'} | text: {content}" for title, content in items]
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH):
            batch = texts[start : start + self.BATCH]
            self._limiter.wait()
            try:
                vectors += self._client.embed_documents(batch, batch_size=self.BATCH)
            except Exception as failure:
                raise LLMError(f"{type(failure).__name__}: {failure}") from failure
            self.characters += sum(len(t) for t in batch)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        self._limiter.wait()
        query = f"task: search result | query: {text}"
        try:
            vector = self._client.embed_query(query)
        except Exception as failure:
            raise LLMError(f"{type(failure).__name__}: {failure}") from failure
        self.characters += len(query)
        return vector
