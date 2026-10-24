"""Telegram 轉接頭的單元測試（ADR-063）。"""

from app.core.notify import telegram
from app.core.notify.base import Notification


def test_to_html_bolds_the_title_escapes_text_and_ends_with_the_link() -> None:
    # 標題粗體放第一行，接著每一行內容，最後一行是官網連結
    # 不是標籤的 & < > 要轉義，不然 Telegram 會把它當成標籤，整則訊息被拒收
    notification = Notification(
        kind="new_scholarship",
        title="R&D <AI> 獎學金",
        lines=("截止 2027-01-15",),
        url="https://example.org/a?x=1&y=2",
    )
    assert telegram.to_html(notification) == (
        "<b>R&amp;D &lt;AI&gt; 獎學金</b>\n"
        "截止 2027-01-15\n"
        '<a href="https://example.org/a?x=1&amp;y=2">官網連結</a>'
    )

    # 內容行也要轉義；網址放在 href="..." 的雙引號裡，所以網址裡的 " 也要轉義
    notification = Notification(
        kind="change",
        title="金額變更",
        lines=("名額 > 10", "學費 & 生活費 < 2 萬歐元"),
        url='https://example.org/?q="x"',
    )
    assert telegram.to_html(notification) == (
        "<b>金額變更</b>\n"
        "名額 &gt; 10\n"
        "學費 &amp; 生活費 &lt; 2 萬歐元\n"
        '<a href="https://example.org/?q=&quot;x&quot;">官網連結</a>'
    )

    # 沒有內容行、也沒有連結：只有粗體標題
    notification = Notification(kind="system", title="斷路器打開")
    assert telegram.to_html(notification) == "<b>斷路器打開</b>"
