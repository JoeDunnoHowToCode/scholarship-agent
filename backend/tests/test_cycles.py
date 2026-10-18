"""申請期日期計算的單元測試。"""

from datetime import UTC, date, datetime

from app.features.scholarships import cycles


def test_to_utc_converts_with_an_iana_timezone() -> None:
    # 巴黎冬天是 UTC+1：1 月 31 日 23:59 巴黎時間＝UTC 22:59
    assert cycles.to_utc(2027, 1, 31, "23:59", "Europe/Paris") == (datetime(2027, 1, 31, 22, 59, tzinfo=UTC), False)
    # 教育部：台北中午 12:00 截止＝UTC 04:00
    assert cycles.to_utc(2026, 2, 13, "12:00", "Asia/Taipei") == (datetime(2026, 2, 13, 4, 0, tzinfo=UTC), False)


def test_to_utc_uses_default_time_2359_when_time_is_missing_or_invalid() -> None:
    # 原文只寫「31 January 2027」沒寫幾點：當天最後一分鐘 23:59 巴黎時間＝UTC 22:59
    expected = (datetime(2027, 1, 31, 22, 59, tzinfo=UTC), False)
    assert cycles.to_utc(2027, 1, 31, None, "Europe/Paris") == expected
    # 模型寫出不存在的時間（25:99）或亂寫格式，也當成 23:59
    assert cycles.to_utc(2027, 1, 31, "25:99", "Europe/Paris") == expected
    assert cycles.to_utc(2027, 1, 31, "noon", "Europe/Paris") == expected


def test_to_utc_assumed_utc_plus_14_when_timezone_is_missing_or_invalid() -> None:
    # 原文沒寫時區：用全世界最早到的 UTC+14，3 月 1 日 23:59＝UTC 09:59，並標記成「假設的」
    expected = (datetime(2027, 3, 1, 9, 59, tzinfo=UTC), True)
    assert cycles.to_utc(2027, 3, 1, None, None) == expected
    # 模型寫出不存在的時區名稱，時間也寫錯：兩個都用預設值
    assert cycles.to_utc(2027, 3, 1, "25:99", "Nowhere/City") == expected


def test_cycle_status_gives_all_four_statuses() -> None:
    # 申請期 2026-11-01 開放、2027-01-31 截止
    opens = datetime(2026, 11, 1, tzinfo=UTC)
    closes = datetime(2027, 1, 31, 22, 59, tzinfo=UTC)
    assert cycles.cycle_status(opens, closes, datetime(2026, 10, 18, tzinfo=UTC), estimated=False) == "upcoming"
    assert cycles.cycle_status(opens, closes, datetime(2026, 12, 1, tzinfo=UTC), estimated=False) == "open"
    assert cycles.cycle_status(opens, closes, closes, estimated=False) == "closed"  # 截止那一刻就算截止
    # 原文沒寫開放日：還沒截止就算開放中
    assert cycles.cycle_status(None, closes, datetime(2026, 10, 18, tzinfo=UTC), estimated=False) == "open"
    # 系統自己推估的明年申請期，不管日期都是 estimated
    assert cycles.cycle_status(opens, closes, datetime(2026, 12, 1, tzinfo=UTC), estimated=True) == "estimated"


def test_next_intake_adds_one_to_every_year() -> None:
    # 入學年度的各種寫法：學年、跨年範圍、單一年份
    assert cycles.next_intake("2026/27") == "2027/28"
    assert cycles.next_intake("2026-2028") == "2027-2029"
    assert cycles.next_intake("2026/2027") == "2027/2028"
    assert cycles.next_intake("2027") == "2028"
    assert cycles.next_intake("Intake 2026/27") == "Intake 2027/28"  # 年份前後的文字保留
    # 兩位數的年份要補零，99 的下一年是 00
    assert cycles.next_intake("2098/99") == "2099/00"
    assert cycles.next_intake("2099/00") == "2100/01"
    # 沒有四位數年份就不知道怎麼推
    assert cycles.next_intake("Fall") is None
    assert cycles.next_intake(None) is None


def test_estimate_next_is_one_year_later() -> None:
    # 今年 2026-11-01 開放、2027-01-31 截止：猜明年同一天同一時間，開放前 30 天開始回原網站檢查
    estimate = cycles.estimate_next(
        datetime(2026, 11, 1, tzinfo=UTC), datetime(2027, 1, 31, 22, 59, tzinfo=UTC), "2027/28"
    )
    assert estimate == cycles.Estimate(
        opens_at=datetime(2027, 11, 1, tzinfo=UTC),
        closes_at=datetime(2028, 1, 31, 22, 59, tzinfo=UTC),
        intake="2028/29",
        recheck_from=date(2027, 10, 2),
    )
    # 沒寫開放日：截止前 90 天開始檢查；閏年 2/29 截止，明年沒有 2/29，改成 2/28
    leap = cycles.estimate_next(None, datetime(2028, 2, 29, 10, 0, tzinfo=UTC), None)
    assert leap == cycles.Estimate(
        opens_at=None,
        closes_at=datetime(2029, 2, 28, 10, 0, tzinfo=UTC),
        intake=None,
        recheck_from=date(2028, 11, 30),
    )
