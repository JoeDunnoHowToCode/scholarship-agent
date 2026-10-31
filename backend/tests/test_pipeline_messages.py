"""每日檢查的系統通知文字（ADR-075、076）：時間都用台灣時間。"""

from datetime import UTC, date, datetime

from app.features.pipeline import report


def test_report_message_tells_whether_and_why_the_check_ran() -> None:
    # 管理者要知道每一輪做了沒、做了什麼；和上一輪之間沒檢查的日子，也要說明為什麼
    title, lines = report.report_message(
        local_date=date(2026, 11, 1),
        started_at=datetime(2026, 11, 1, 0, 40, tzinfo=UTC),  # 台灣 11-01 08:40
        finished_at=datetime(2026, 11, 1, 19, 10, tzinfo=UTC),  # 台灣 11-02 03:10：拖過午夜，寫出日期
        sources={"extracted": 16, "unchanged": 113, "failed": 18, "skipped": 3, "catalogue": 1},
        new_events=2,
        skipped=[(date(2026, 10, 30), True), (date(2026, 10, 31), False)],
    )
    assert title == "每日檢查完成：11-01"
    assert lines == [
        "08:40 開始，11-02 03:10 收尾",
        "151 個來源：有變 16、沒變 113、抓不到 18、其他 4",
        "這輪產生 2 則通知",
        "10-30 沒有單獨檢查：在等前一輪收尾",
        "10-31 沒有檢查：那天電腦沒開或沒有網路",
    ]
