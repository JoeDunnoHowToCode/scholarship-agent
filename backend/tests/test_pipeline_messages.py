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


def test_waiting_message_says_why_today_has_not_started() -> None:
    title, lines = report.waiting_message(
        today=date(2026, 11, 1),
        previous_date=date(2026, 10, 31),
        previous_started=datetime(2026, 10, 31, 3, 40, tzinfo=UTC),  # 台灣 10-31 11:40
        now=datetime(2026, 10, 31, 23, 40, tzinfo=UTC),  # 台灣 11-01 07:40：開始 20 小時
    )
    assert title == "11-01 的檢查還沒開始"
    assert lines == ["在等 10-31 那輪收尾（已經開始 20 小時）", "收尾後 15 分鐘內開始"]


def test_stale_message_warns_and_says_today_starts_anyway() -> None:
    title, lines = report.stale_message(
        previous_date=date(2026, 10, 30),
        previous_started=datetime(2026, 10, 29, 22, 40, tzinfo=UTC),  # 台灣 10-30 06:40
        now=datetime(2026, 10, 31, 0, 40, tzinfo=UTC),  # 台灣 10-31 08:40：開始 26 小時
    )
    assert title == "10-30 那輪開始 26 小時還沒收尾"
    assert lines == [
        "可能是收尾壞了，或電腦關機太久；今天照常開始",
        "查原因：backend/data/logs/worker.log",
    ]


def test_report_counts_sources_whose_only_changes_were_unrelated() -> None:
    # ADR-079：只有無關內容變了、沒重抽的來源算「沒變」，另外註明有幾個，用來看重抽比率有沒有下降
    _, lines = report.report_message(
        local_date=date(2026, 11, 5),
        started_at=datetime(2026, 11, 5, 0, 10, tzinfo=UTC),
        finished_at=datetime(2026, 11, 5, 2, 0, tzinfo=UTC),
        sources={"extracted": 5, "unchanged": 100, "noise": 9, "failed": 18},
        new_events=0,
        skipped=[],
    )
    assert lines[1] == "132 個來源：有變 5、沒變 109（其中 9 個只有無關內容變了）、抓不到 18、其他 0"


def test_unreachable_and_recovered_messages() -> None:
    # ADR-080：標記時告訴你是哪個來源、最後的錯誤、資料停在哪天，以及之後怎麼處理
    title, lines = report.unreachable_message(
        "MAGMA", "https://www.magma-erasmusmundus.eu/", "ConnectError: nodename nor servname provided", date(2026, 10, 11)
    )
    assert title == "連續 3 天抓不到：MAGMA"
    assert lines == [
        "網址：https://www.magma-erasmusmundus.eu/",
        "最後的錯誤：ConnectError: nodename nor servname provided",
        "資料停在 10-11",
        "之後每 7 天再試一次，恢復了會通知你",
    ]
    # 從來沒抓到過的來源
    assert report.unreachable_message("X", "https://x.eu/", "timed out", None)[1][2] == "還沒抓到過資料"
    title, lines = report.recovered_message("SpreeAfrica", "http://www.spreeafrica.com/")
    assert title == "抓得到了：SpreeAfrica"
    assert lines == ["網址：http://www.spreeafrica.com/", "回到每天檢查"]
