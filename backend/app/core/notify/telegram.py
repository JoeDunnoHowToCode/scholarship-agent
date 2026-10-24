"""Telegram 轉接頭（ADR-063）：把結構化通知排成 Telegram 的 HTML、切成 4096 字以內。"""

import html

from app.core.notify.base import Notification
from app.core.notify.telegram_api import TelegramError, call
from app.shared.settings import settings


def _one_line(text: str) -> str:
    """把文字裡的換行換成空格：每個標籤都在同一行，依行切段才不會把標籤切斷。"""
    return " ".join(text.splitlines())


def to_html(notification: Notification) -> str:
    """標題粗體放第一行，接著每一行內容；有網址就在最後一行放官網連結。"""
    # 不是標籤的 & < > 要換成 &amp; &lt; &gt;，否則 Telegram 會當成標籤而拒收整則訊息
    # quote=False：內文裡的引號不用換
    parts = [f"<b>{html.escape(_one_line(notification.title), quote=False)}</b>"]
    parts += [html.escape(_one_line(line), quote=False) for line in notification.lines]
    if notification.url:
        # 網址放在 href="..." 的雙引號裡，所以 " 也要換成 &quot;（html.escape 預設會換引號）
        parts.append(f'<a href="{html.escape(notification.url)}">官網連結</a>')
    return "\n".join(parts)


def split_message(text: str, limit: int = 4096) -> list[str]:
    """Telegram 一則訊息最多 4096 字：太長就在換行處切成好幾則，每則盡量多裝幾行。"""
    # 先拆成一段一段：通常一行就是一段；一行就超過上限的，只好每 limit 個字硬切
    pieces: list[str] = []
    for line in text.split("\n"):
        # 空行切不出任何一段，補一個空字串，空行才會留著
        pieces += [line[i : i + limit] for i in range(0, len(line), limit)] or [""]
    chunks: list[str] = []
    current = ""  # 正在裝的這一則
    for piece in pieces:
        # 裝得下就接在後面；中間的換行也算一個字
        if current and len(current) + 1 + len(piece) <= limit:
            current += "\n" + piece
        else:
            if current:  # 空的不收（Telegram 不收空訊息）
                chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks


class TelegramNotifier:
    """Telegram 轉接頭（實作 base.Notifier）：排成 HTML、切成 4096 字以內，一段一段送到你的聊天。"""

    def __init__(self, chat_id: str) -> None:
        self.chat_id = chat_id

    def send(self, notification: Notification) -> None:
        for chunk in split_message(to_html(notification)):
            call(
                "sendMessage",
                {
                    "chat_id": self.chat_id,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "link_preview_options": {"is_disabled": True},  # 不顯示網頁預覽，訊息比較精簡
                },
            )


def notifier_from_settings() -> TelegramNotifier:
    """用 backend/.env 的設定建立轉接頭；還沒設定聊天 ID 就丟 TelegramError（送出工作會先停下）。"""
    if not settings.telegram_chat_id:
        raise TelegramError(404, "backend/.env 沒有 TELEGRAM_CHAT_ID：先執行 uv run python -m app.core.notify.setup")
    return TelegramNotifier(settings.telegram_chat_id)
