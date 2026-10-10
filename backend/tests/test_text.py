"""網頁轉文字與內容雜湊的單元測試（ADR-027）。"""

from app.core.fetch import text


def test_html_to_text_excludes_script_and_style() -> None:
    # script、style 是程式碼和樣式，不是頁面上看得到的文字
    html = "<p>Hello</p><script>var x = 1;</script><style>p { color: red; }</style>"
    assert text.html_to_text(html) == "Hello"
