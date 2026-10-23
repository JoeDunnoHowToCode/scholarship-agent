"""錯誤分類的單元測試（ADR-056）：重試、跳過、暫停 AI。"""

import httpx
import pytest
from google.genai.errors import ClientError, ServerError

from app.core.fetch.base import BlockedError
from app.core.llm.gemini import ExtractionError, LLMError, MissingApiKeyError
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


@pytest.mark.parametrize(
    "error",
    [
        BlockedError("captcha"),
        website_error(404),
        ExtractionError("重試 2 次仍不符合 ScholarshipExtraction"),
        KeyError("deadline"),
    ],
    ids=["blocked", "website_404", "ai_output_invalid", "unknown"],
)
def test_skip_errors_that_will_not_fix_themselves(error: BaseException) -> None:
    # 被擋（抓取程式已標需人工，ADR-028）、頁面不存在、AI 重試後資料仍驗證不過、程式沒料到的錯誤：
    # 再試也一樣，記下原因就好
    assert errors.classify(error) == "skip"


@pytest.mark.parametrize(
    "error",
    [
        caused_by(BlockedError("captcha"), httpx.ConnectError("連不上網站")),
        caused_by(website_error(404), httpx.ConnectError("連不上網站")),
        caused_by(ExtractionError("重試 2 次仍不符合"), httpx.ConnectError("連不上網站")),
    ],
    ids=["blocked", "website_404", "ai_output_invalid"],
)
def test_skip_outer_error_wins_over_a_temporary_cause(error: BaseException) -> None:
    # 由外往內看，第一個認得的例外就決定結果：外層已經判斷成「再試也沒用」，就不管裡面的連線錯誤
    assert errors.classify(error) == "skip"


@pytest.mark.parametrize("code", [402, 401, 403], ids=["gemini_402", "gemini_401", "gemini_403"])
def test_pause_ai_when_the_gemini_account_has_a_problem(code: int) -> None:
    # 額度用完（402）或金鑰有問題（401、403）：之後每件 AI 工作都會失敗，要整個暫停，等你處理
    gemini = ClientError(code, {"error": {"code": code, "message": "測試用的錯誤"}})
    assert errors.classify(caused_by(LLMError(f"ClientError: {code}"), gemini)) == "pause_ai"
    # LangChain 可能在中間再包一層（例如 ChatGoogleGenerativeAIError），一樣要認得出來
    middle = caused_by(RuntimeError("LangChain 包的錯誤"), gemini)
    assert errors.classify(caused_by(LLMError(f"ClientError: {code}"), middle)) == "pause_ai"


def test_pause_ai_when_the_api_key_is_missing() -> None:
    # 沒設定 Gemini 金鑰：每件 AI 工作都會失敗
    assert errors.classify(MissingApiKeyError("沒有 Gemini 金鑰")) == "pause_ai"


def test_pause_ai_when_the_cost_limit_is_reached() -> None:
    # 這件工作的 AI 費用超過上限：暫停所有 AI 工作，避免超出預算（ADR-013）
    assert errors.classify(errors.CostLimitError("超過這次執行的上限 US$1.00")) == "pause_ai"


def test_pause_ai_when_the_key_is_invalid_or_the_model_does_not_exist() -> None:
    # 金鑰無效時 Gemini 常回 400、內容寫 API_KEY_INVALID（不一定是 401）；模型名稱打錯回 404
    # 兩種都是設定問題，之後每件 AI 工作都會失敗：整個暫停（ADR-056「金鑰有問題」）
    bad_key = ClientError(
        400,
        {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                   "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}},
    )
    assert errors.classify(caused_by(LLMError("ClientError: 400"), bad_key)) == "pause_ai"
    no_model = ClientError(404, {"error": {"code": 404, "message": "models/gemini-x is not found", "status": "NOT_FOUND"}})
    assert errors.classify(caused_by(LLMError("ClientError: 404"), no_model)) == "pause_ai"
    # 其他的 400（例如這一次送出去的內容太大）只影響這一件：跳過
    too_big = ClientError(
        400, {"error": {"code": 400, "message": "Request payload size exceeds the limit", "status": "INVALID_ARGUMENT"}}
    )
    assert errors.classify(caused_by(LLMError("ClientError: 400"), too_big)) == "skip"
