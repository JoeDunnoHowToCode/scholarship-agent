"""申請期日期計算的單元測試。"""

from datetime import UTC, datetime

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
