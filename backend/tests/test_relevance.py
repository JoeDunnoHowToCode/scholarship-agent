"""要不要重抽（ADR-079）：只看和獎學金有關的段落。"""

from datetime import UTC, datetime, timedelta

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


def test_decide_reextracts_only_when_needed() -> None:
    now = datetime(2026, 11, 4, tzinfo=UTC)
    text = "Application period: 1 November 2026 – 12 February 2027."
    quotes = ["Application period: 1 November 2026 – 12 February 2027."]
    recent = now - timedelta(days=3)
    # 相關段落沒變、引用都還在、最近才抽過：略過（只有無關內容變了）
    assert relevance.decide("a", "a", quotes, text, recent, now) == "skip"
    # 相關段落變了：重抽
    assert relevance.decide("a", "b", quotes, text, recent, now) == "relevant_changed"
    # 已存的引用有一句在新版找不到（例如截止日那句被改掉）：重抽
    changed = "Application period: 1 November 2026 – 26 February 2027."
    assert relevance.decide("a", "a", quotes, changed, recent, now) == "quote_missing"
    # 上次真的抽取超過 30 天（含剛好 30 天）：整份重抽一次
    assert relevance.decide("a", "a", quotes, text, now - timedelta(days=30), now) == "too_old"
    # 沒有抽取時間的舊資料：當成太久
    assert relevance.decide("a", "a", quotes, text, None, now) == "too_old"
