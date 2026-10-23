"""檢查頻率的單元測試（ADR-058）：每個來源多久回官網看一次。"""

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
