"""網頁轉文字與內容雜湊的單元測試（ADR-027）。"""

from app.core.fetch import text


def test_html_to_text_excludes_script_and_style() -> None:
    # script、style 是程式碼和樣式，不是頁面上看得到的文字
    html = "<p>Hello</p><script>var x = 1;</script><style>p { color: red; }</style>"
    assert text.html_to_text(html) == "Hello"


def test_html_to_text_puts_block_elements_on_separate_lines() -> None:
    # 兩個段落不能黏成「AB」
    assert text.html_to_text("<p>A</p><p>B</p>") == "A\nB"


def test_html_to_text_joins_inline_split_words() -> None:
    # Chevening 的原始碼把年份拆成 <span>202</span><span>7</span>，要接回 2027
    html = "<p>Applications for <span>202</span><span>7</span>-<span>202</span><span>8</span></p>"
    assert text.html_to_text(html) == "Applications for 2027-2028"


def test_content_hash_ignores_whitespace_differences() -> None:
    # 只差空白或換行算「沒變」；字不一樣才算「有變」
    assert text.content_hash("Closed  for\napplications ") == text.content_hash(
        "Closed for applications"
    )
    assert text.content_hash("Closed for applications") != text.content_hash(
        "Open for applications"
    )
