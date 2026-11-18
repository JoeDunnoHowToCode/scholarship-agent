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
