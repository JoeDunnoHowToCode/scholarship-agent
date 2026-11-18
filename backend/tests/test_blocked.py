"""被擋的來源什麼時候自動再試（ADR-116）：429 七天、403 三十天；robots.txt 與 captcha 等人工。"""

from datetime import date

import pytest

from app.features.sources import fetch

TODAY = date(2026, 11, 19)


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("429", date(2026, 11, 26)),  # 太頻繁：一週後再試
        ("403", date(2026, 12, 19)),  # 拒絕存取：一個月後再試一次
        ("robots.txt 禁止", None),  # 網站明說不要爬：尊重，不再試
        ("captcha", None),  # 要真人驗證：不能繞過，不再試
    ],
)
def test_retry_date_depends_on_why_the_site_blocked_us(reason: str, expected: date | None) -> None:
    assert fetch.retry_on(reason, None, TODAY) == expected


@pytest.mark.parametrize(
    ("retry_after", "expected"),
    [
        ("172800", date(2026, 11, 21)),  # 伺服器說 2 天後再來：照它
        ("60", date(2026, 11, 20)),  # 不到一天：至少隔一天，每天最多打擾一次
        ("2592000", date(2026, 11, 26)),  # 30 天：最多等 7 天，和沒給時一樣
        ("Fri, 21 Nov 2026 08:00:00 GMT", date(2026, 11, 21)),  # 也可能寫成日期
        ("soon", date(2026, 11, 26)),  # 看不懂就當沒給
    ],
)
def test_a_429_follows_the_servers_retry_after_within_one_to_seven_days(retry_after: str, expected: date) -> None:
    # EACEA 11-18 在每 5 秒一頁時回 429；伺服器有說多久後再來，就照它
    assert fetch.retry_on("429", retry_after, TODAY) == expected
