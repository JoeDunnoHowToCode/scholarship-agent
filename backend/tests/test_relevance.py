"""要不要重抽（ADR-079）：只看和獎學金有關的段落。"""

from app.features.documents.chunking import chunk_html
from app.features.scholarships import relevance

PAGE = """<h2>Latest news</h2><p>{news}</p>
<h2>Scholarships</h2><p>Erasmus Mundus scholarships cover tuition and a monthly allowance of 1,400 EUR.</p>
<h2>How to apply</h2><p>Application period: 1 November 2026 – {deadline}.</p>"""


def fingerprint(news: str, deadline: str = "12 February 2027") -> str:
    return relevance.fingerprint(chunk_html(PAGE.format(news=news, deadline=deadline)))


def test_fingerprint_ignores_unrelated_changes_but_not_related_ones() -> None:
    before = fingerprint("Our students visited Brussels on 2 November.")
    # 最新消息換了內容（每天在變的雜訊）：指紋不變
    assert fingerprint("Our students visited Lisbon on 3 November.") == before
    # 只有空白不同：指紋不變
    assert fingerprint("Our  students visited   Brussels on 2 November.") == before
    # 截止日改了：指紋不同
    assert fingerprint("Our students visited Brussels on 2 November.", deadline="26 February 2027") != before
    # 最新消息裡寫截止延長：這一段也算相關，指紋不同
    assert fingerprint("The application deadline is extended to 26 February 2027.") != before
    # 指紋不是空的（有相關段落）
    assert before
