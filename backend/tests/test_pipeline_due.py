"""檢查頻率的單元測試（ADR-058）：每個來源多久回官網看一次。"""

from datetime import date

import pytest

from app.features.pipeline import due


@pytest.mark.parametrize(
    ("status", "stale", "expected"),
    [
        (None, False, "daily"),
        ("active", False, "daily"),
        ("archived", False, "weekly"),
        ("archived", True, "monthly"),
    ],
    ids=["no_scholarship_yet", "active", "archived", "archived_stale"],
)
def test_frequency_follows_the_scholarship_status(status: str | None, stale: bool, expected: str) -> None:
    # 還沒抽出獎學金（目錄頁、剛加的學程）和使用中的：每天看
    # 封存的：每週看；資料過舊的（最近一次真的截止日超過 24 個月）：每月看
    assert due.frequency_for(status, stale) == expected


def test_daily_due_unless_already_checked_today() -> None:
    today = date(2026, 10, 23)  # 台灣時間的日期
    assert due.is_due("daily", None, today) is True  # 從沒檢查過
    assert due.is_due("daily", date(2026, 10, 22), today) is True  # 昨天看過，今天還沒看
    assert due.is_due("daily", today, today) is False  # 今天已經看過
