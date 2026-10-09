"""Gemini 轉接頭（ADR-010、011、015）：透過 LangChain 呼叫 Gemini，回傳結構化資料。"""

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, SecretStr


class MissingApiKeyError(RuntimeError):
    """沒有設定 Gemini 金鑰。"""


class GeminiLLM:
    """符合 StructuredLLM 插座的 Gemini 實作。"""

    def __init__(self, model: str, api_key: SecretStr | None) -> None:
        if api_key is None or not api_key.get_secret_value():
            raise MissingApiKeyError(
                "沒有 Gemini 金鑰：請在 backend/.env 設定 GOOGLE_API_KEY=你的金鑰"
            )
        # 金鑰明確傳進來：pydantic-settings 讀 .env 時不會放進環境變數，LangChain 自己讀不到
        # 不設定 temperature：Gemini 3 系列官方建議維持預設值
        self._chat = ChatGoogleGenerativeAI(model=model, api_key=api_key)

    def extract[M: BaseModel](self, prompt: str, schema: type[M]) -> M:
        # 預設 method="json_schema"，也就是 Gemini 原生的結構化輸出（ADR-011）
        result = self._chat.with_structured_output(schema).invoke(prompt)
        if not isinstance(result, schema):
            raise TypeError(f"模型回傳的不是 {schema.__name__}，而是 {type(result).__name__}")
        return result
