"""申請期日期計算的單元測試。"""

from datetime import UTC, datetime

from app.features.scholarships import cycles


def test_to_utc_converts_with_an_iana_timezone() -> None:
    # 巴黎冬天是 UTC+1：1 月 31 日 23:59 巴黎時間＝UTC 22:59
    assert cycles.to_utc(2027, 1, 31, "23:59", "Europe/Paris") == (datetime(2027, 1, 31, 22, 59, tzinfo=UTC), False)
    # 教育部：台北中午 12:00 截止＝UTC 04:00
    assert cycles.to_utc(2026, 2, 13, "12:00", "Asia/Taipei") == (datetime(2026, 2, 13, 4, 0, tzinfo=UTC), False)
