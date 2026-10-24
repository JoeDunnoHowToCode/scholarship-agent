"""Telegram Bot API 的 HTTP 呼叫（ADR-063）：https://api.telegram.org/bot<token>/方法名稱。

token 只從設定讀（backend/.env），絕不印出來；呼叫的網址含 token，所以錯誤訊息一律不放網址。
"""

import json
import time
from typing import Any

import httpx

from app.core.fetch.base import TemporaryFetchError
from app.shared.settings import settings

API = "https://api.telegram.org"
MAX_WAIT_SECONDS = 60  # 被限速（429）時，要等的秒數在這以內就等一下再送一次


class TelegramError(RuntimeError):
    """Telegram 回 ok=false；code 是錯誤碼（例如 400 格式錯、401 token 錯、403 被封鎖、429 限速）。"""

    def __init__(self, code: int, description: str) -> None:
        super().__init__(f"Telegram {code}：{description}")
        self.code = code
        self.description = description


def call(method: str, params: dict[str, Any]) -> Any:
    """呼叫一個 Bot API 方法，回傳 result；網路出錯丟 TemporaryFetchError（第 7 天的分類會重試）。"""
    if settings.telegram_bot_token is None:
        raise TelegramError(401, "backend/.env 沒有 TELEGRAM_BOT_TOKEN")
    url = f"{API}/bot{settings.telegram_bot_token.get_secret_value()}/{method}"
    for attempt in range(2):
        try:
            response = httpx.post(url, json=params, timeout=30)
            body = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            # from None：不把原本的例外接在後面，以免哪天它的訊息裡帶著含 token 的網址
            raise TemporaryFetchError(f"Telegram 連線失敗：{type(error).__name__}") from None
        if body.get("ok"):
            return body["result"]
        code = int(body.get("error_code") or response.status_code)
        wait = (body.get("parameters") or {}).get("retry_after")
        if code == 429 and attempt == 0 and isinstance(wait, int) and wait <= MAX_WAIT_SECONDS:
            time.sleep(wait)  # 被限速：照 Telegram 說的秒數等一下，再送一次
            continue
        if code >= 500:
            raise TemporaryFetchError(f"Telegram 暫時出錯（{code}）")
        raise TelegramError(code, str(body.get("description", "")))
    raise TelegramError(429, "被限速，等過一次仍然失敗")
