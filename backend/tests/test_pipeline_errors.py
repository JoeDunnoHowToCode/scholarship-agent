"""錯誤分類的單元測試（ADR-056）：重試、跳過、暫停 AI。"""

import httpx
import pytest
from google.genai.errors import ClientError, ServerError

from app.core.llm.gemini import LLMError
from app.features.pipeline import errors


def caused_by(outer: BaseException, inner: BaseException) -> BaseException:
    """模擬 raise outer from inner：Python 把原本的錯誤存在 outer.__cause__。"""
    outer.__cause__ = inner
    return outer


def raised_while_handling(outer: BaseException, inner: BaseException) -> BaseException:
    """模擬在 except 區塊裡直接 raise outer（沒寫 from）：Python 把原本的錯誤存在 outer.__context__。"""
    outer.__context__ = inner
    return outer


def website_error(status: int) -> httpx.HTTPStatusError:
    """官網回錯誤狀態碼時，httpx 的 raise_for_status() 丟出的例外。"""
    request = httpx.Request("GET", "https://www.example.org/scholarship")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"{status}", request=request, response=response)


def wrapped(error: BaseException, layers: int) -> BaseException:
    """把 error 再包 layers 層，每一層都是 raise RuntimeError(...) from 下一層。"""
    for _ in range(layers):
        error = caused_by(RuntimeError("又包了一層"), error)
    return error


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("連不上網站"),
        httpx.ReadTimeout("等太久沒有回應"),
        website_error(503),
        # 我們的 Gemini 轉接頭把 Google 的錯誤包成 LLMError，原本的錯誤在 __cause__
        caused_by(
            LLMError("ClientError: 429 RESOURCE_EXHAUSTED"),
            ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}}),
        ),
        caused_by(
            LLMError("ServerError: 503 UNAVAILABLE"),
            ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE"}}),
        ),
        caused_by(LLMError("ReadTimeout: 等太久沒有回應"), httpx.ReadTimeout("等太久沒有回應")),
        # 沒寫 from 的包法：原本的錯誤在 __context__
        raised_while_handling(
            RuntimeError("呼叫模型失敗"),
            ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE"}}),
        ),
    ],
    ids=[
        "network",
        "timeout",
        "website_5xx",
        "gemini_429",
        "gemini_503",
        "gemini_timeout",
        "gemini_503_in_context",
    ],
)
def test_retry_temporary_errors(error: BaseException) -> None:
    # 網路斷線、逾時、網站或 Gemini 暫時出問題：等一下再試通常就會好
    assert errors.classify(error) == "retry"


def test_retry_cause_is_searched_at_most_ten_links_deep() -> None:
    # 從最外層算起最多看 10 個例外：第 10 個是網路錯誤找得到，第 11 個就不找了
    assert errors.classify(wrapped(httpx.ConnectError("連不上網站"), 9)) == "retry"
    assert errors.classify(wrapped(httpx.ConnectError("連不上網站"), 10)) == "skip"


def test_retry_search_stops_on_a_looping_chain() -> None:
    # 兩個例外互相指向對方（循環）：找不到可以重試的原因，也不會卡在無限迴圈
    first = RuntimeError("第一個")
    second = caused_by(RuntimeError("第二個"), first)
    caused_by(first, second)
    assert errors.classify(first) == "skip"
