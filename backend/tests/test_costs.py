"""費用紀錄與每月上限（ADR-013、049、089）。"""

from datetime import UTC, datetime

from app.features.costs.usage import month_start, over_cap


def test_month_follows_the_taipei_calendar() -> None:
    # 台灣時間 11-15 11:00 → 本月從台灣時間 11-01 00:00 算起，也就是 UTC 10-31 16:00
    assert month_start(datetime(2026, 11, 15, 3, 0, tzinfo=UTC)) == datetime(2026, 10, 31, 16, 0, tzinfo=UTC)
    # UTC 11-30 17:00 在台灣已經是 12-01 01:00：屬於 12 月
    assert month_start(datetime(2026, 11, 30, 17, 0, tzinfo=UTC)) == datetime(2026, 11, 30, 16, 0, tzinfo=UTC)


def test_cap_is_reached_at_the_exact_amount() -> None:
    # 每月上限 NT$7,000 ＝ US$218.75（匯率 32）
    assert over_cap(218.75, 7000) is True
    assert over_cap(218.74, 7000) is False
