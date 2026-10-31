"""每日檢查的系統通知（ADR-075、076）：每日檢查報告、在等前一輪收尾、前一輪太久。

這裡只產生文字（純函式，好測試）；tick 與收尾工作把它寫成系統事件，各自一則、不併進摘要。
"""

from datetime import date, datetime

# 系統通知的標題，以及內容的每一行
Message = tuple[str, list[str]]


def report_message(
    local_date: date,
    started_at: datetime,
    finished_at: datetime,
    sources: dict[str, int],
    new_events: int,
    skipped: list[tuple[date, bool]],
) -> Message:
    """每日檢查報告：哪一天、何時開始與收尾（台灣時間）、來源結果、這輪產生幾則通知。

    skipped：和上一輪之間沒有單獨檢查的日子，以及那天是不是在等前一輪收尾。
    """
    return "", []


def waiting_message(today: date, previous_date: date, previous_started: datetime, now: datetime) -> Message:
    """今天的檢查還沒開始：在等前一輪收尾。"""
    return "", []


def stale_message(previous_date: date, previous_started: datetime, now: datetime) -> Message:
    """前一輪開始太久還沒收尾：可能壞了，今天照常開始。"""
    return "", []
