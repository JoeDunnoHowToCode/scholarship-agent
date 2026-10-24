"""Telegram 轉接頭（ADR-063）：把結構化通知排成 Telegram 的 HTML、切成 4096 字以內。"""

import html

from app.core.notify.base import Notification


def to_html(notification: Notification) -> str:
    """標題粗體放第一行，接著每一行內容；有網址就在最後一行放官網連結。"""
    # 不是標籤的 & < > 要換成 &amp; &lt; &gt;，否則 Telegram 會當成標籤而拒收整則訊息
    # quote=False：內文裡的引號不用換
    parts = [f"<b>{html.escape(notification.title, quote=False)}</b>"]
    parts += [html.escape(line, quote=False) for line in notification.lines]
    if notification.url:
        # 網址放在 href="..." 的雙引號裡，所以 " 也要換成 &quot;（html.escape 預設會換引號）
        parts.append(f'<a href="{html.escape(notification.url)}">官網連結</a>')
    return "\n".join(parts)
