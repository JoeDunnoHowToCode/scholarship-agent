"""錯誤分類（ADR-056）：背景工作出錯時，決定要重試、跳過（記下原因），還是打開斷路器暫停 AI。"""

import socket
import ssl
from typing import Literal

import httpx
from google.genai.errors import APIError

from app.core.fetch.base import BlockedError, PageGone, TemporaryFetchError
from app.core.llm.gemini import ExtractionError, MissingApiKeyError

# fail：當天直接算失敗、不重試（重試也不會好）；跨天仍照 ADR-080 數「連續幾天失敗」
Kind = Literal["retry", "skip", "pause_ai", "fail"]

# 最多往裡面看幾個例外（含最外層）；例外互相指向（循環）時，也會在這裡停下來
MAX_LINKS = 10


class CostLimitError(RuntimeError):
    """這件工作的 AI 費用超過上限。"""


def classify(error: BaseException) -> Kind:
    """由外往內一個一個看，第一個認得的例外決定結果；都認不得就跳過（記下原因，不重試）。

    我們的 Gemini 轉接頭會把 Google 的錯誤包成 LLMError，原本的錯誤（含狀態碼）在裡面。
    """
    # 先往裡面找有沒有「重試也不會好」的原因：httpx 把它包在 ConnectError 裡，外層會被當成一般連線問題
    if _hopeless(error):
        return "fail"
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
    # 下面三種情況，之後每件 AI 工作都會失敗：打開斷路器，暫停所有 AI 工作，等你處理
    if isinstance(error, (CostLimitError, MissingApiKeyError)):
        return "pause_ai"  # 費用超過上限、沒設定金鑰
    if isinstance(error, APIError) and error.code in (401, 402, 403, 404):
        return "pause_ai"  # Gemini 金鑰有問題（401、403）、額度用完（402）、模型名稱錯（404）
    if isinstance(error, APIError) and error.code == 400 and "API_KEY_INVALID" in str(error):
        return "pause_ai"  # 金鑰無效時 Gemini 常回 400，內容寫 API_KEY_INVALID
    if isinstance(error, APIError) and (error.code == 429 or error.code >= 500):
        return "retry"  # Gemini 限速（429）或 Google 那邊暫時出錯（5xx）
    if isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
        return "retry"  # 逾時或連不上（ConnectError 也算 NetworkError）
    if isinstance(error, TemporaryFetchError):
        return "retry"  # 網站暫時讀不到，例如 robots.txt 回 5xx
    if isinstance(error, httpx.HTTPStatusError):  # 官網回錯誤狀態碼
        if error.response.status_code >= 500:
            return "retry"  # 官網暫時出錯
        if error.response.status_code >= 400:
            return "skip"  # 例如 404 頁面不存在：再試也一樣
    if isinstance(error, (BlockedError, ExtractionError)):
        # 被擋：抓取程式已經把來源標成需人工（ADR-028）
        # ExtractionError：AI 重試後抽出的資料仍然驗證不過
        return "skip"
    return None


def _hopeless(error: BaseException) -> bool:
    """網域不存在、對方憑證驗證失敗、對方用太舊的加密協商：都要對方修，當天重試沒用（11-08 使用者要求）。"""
    current: BaseException | None = error
    for _ in range(MAX_LINKS):
        if current is None:
            return False
        if isinstance(current, PageGone):
            return True  # 首頁 404、410：重試也一樣（11-09 使用者選 C）
        if isinstance(current, socket.gaierror) and current.errno == socket.EAI_NONAME:
            return True  # 網域查不到（暫時查不到是 EAI_AGAIN，照舊重試）
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        if isinstance(current, ssl.SSLError) and getattr(current, "reason", None) == "UNSAFE_LEGACY_RENEGOTIATION_DISABLED":
            return True
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return False


def root_cause(error: BaseException) -> BaseException:
    """最裡面的原因（例如 httpx.ConnectError 裡的 socket.gaierror），錯誤說明用它才看得出是什麼問題。"""
    current = error
    for _ in range(MAX_LINKS):
        inner = current.__cause__ if current.__cause__ is not None else current.__context__
        if inner is None:
            break
        current = inner
    return current
