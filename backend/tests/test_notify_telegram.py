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


def test_split_message_cuts_at_line_breaks_within_the_limit() -> None:
    # 先用上限 10 個字，例子比較好讀
    # 沒超過上限就原樣回傳一則（剛好 10 個字也算沒超過）
    assert telegram.split_message("abcd\nefghi", limit=10) == ["abcd\nefghi"]

    # 超過了：只在換行處切，整行裝進同一則；行跟行中間的換行也算一個字
    # 4 + 1 + 5 = 10，剛好裝得下
    assert telegram.split_message("abcd\nefghi\njk", limit=10) == ["abcd\nefghi", "jk"]
    # 5 + 1 + 5 = 11，裝不下，第二行換到下一則
    assert telegram.split_message("abcde\nfghij\nk", limit=10) == ["abcde", "fghij\nk"]

    # 一行就超過上限：只好每 10 個字硬切，最後一段比較短，後面的行照樣接上去
    assert telegram.split_message("ab\n" + "x" * 25 + "\ncd", limit=10) == [
        "ab",
        "x" * 10,
        "x" * 10,
        "xxxxx\ncd",
    ]

    # 切點剛好在空行：不會多出空的一則（Telegram 不收空訊息）
    assert telegram.split_message("abcdefghij\n\nklmnopqrst", limit=10) == [
        "abcdefghij",
        "klmnopqrst",
    ]

    # 實際的長度：300 行，每行 20 個字（例如「000 獎學金截止 2027-01-15」），用預設上限 4096
    # 一則最多裝 195 行（195 × 20 + 194 個換行 = 4094 字），所以切成 2 則
    text = "\n".join(f"{i:03d} 獎學金截止 2027-01-15" for i in range(300))
    chunks = telegram.split_message(text)
    assert len(chunks) == 2
    assert all(len(chunk) <= 4096 for chunk in chunks)
    assert "\n".join(chunks) == text


def test_split_message_keeps_blank_lines_inside_a_chunk() -> None:
    # 空行也是一行（例如摘要裡分隔各組的空行），切段時要留著，不能被吃掉
    assert telegram.split_message("ab\n\ncd\nefghijklmn", limit=10) == [
        "ab\n\ncd",
        "efghijklmn",
    ]


def test_html_keeps_each_tag_on_one_line() -> None:
    # 標題或內容行裡夾著換行時，依行切段可能把 <b>…</b> 切成兩則，Telegram 會拒收（400）；
    # 換成空格，每個標籤就都在同一行（子 agent 實作時提出的風險）
    note = Notification(kind="change", title="名稱\n第二行", lines=("金額：\n每月 1,400 歐元",))
    assert telegram.to_html(note) == "<b>名稱 第二行</b>\n金額： 每月 1,400 歐元"
