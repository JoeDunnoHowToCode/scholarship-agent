"""錯誤分類（ADR-056）：背景工作出錯時，決定要重試、跳過（記下原因），還是打開斷路器暫停 AI。"""

from typing import Literal

import httpx
from google.genai.errors import APIError

Kind = Literal["retry", "skip", "pause_ai"]

# 最多往裡面看幾個例外（含最外層）；例外互相指向（循環）時，也會在這裡停下來
MAX_LINKS = 10


def classify(error: BaseException) -> Kind:
    """由外往內一個一個看，第一個認得的例外決定結果；都認不得就跳過（記下原因，不重試）。

    我們的 Gemini 轉接頭會把 Google 的錯誤包成 LLMError，原本的錯誤（含狀態碼）在裡面。
    """
    current: BaseException | None = error
    for _ in range(MAX_LINKS):
        if current is None:
            break
        kind = _kind_of(current)
        if kind is not None:
            return kind
        # raise 新例外 from 原本的錯誤：原本的錯誤存在 __cause__
        # 在 except 裡直接 raise 新例外（沒寫 from）：原本的錯誤存在 __context__
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return "skip"


def _kind_of(error: BaseException) -> Kind | None:
    """只看這一個例外：認得就回傳處理方式，認不得回傳 None，讓 classify 繼續往裡面找。"""
    if isinstance(error, APIError) and (error.code == 429 or error.code >= 500):
        return "retry"  # Gemini 限速（429）或 Google 那邊暫時出錯（5xx）
    if isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
        return "retry"  # 逾時或連不上（ConnectError 也算 NetworkError）
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code >= 500:
        return "retry"  # 官網暫時出錯
    return None
