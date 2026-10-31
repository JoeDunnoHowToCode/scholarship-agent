"""每日檢查的系統通知（ADR-075、076）：每日檢查報告、在等前一輪收尾、前一輪太久。

這裡只產生文字（純函式，好測試）；tick 與收尾工作把它寫成系統事件，各自一則、不併進摘要。
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# 系統通知的標題，以及內容的每一行
Message = tuple[str, list[str]]


def day(value: date) -> str:
    """日期寫成 11-01。"""
    return value.strftime("%m-%d")


def clock(moment: datetime, local_date: date) -> str:
    """台灣時間；不在這一輪那天的（例如拖過午夜），前面加上日期。"""
    taipei = moment.astimezone(TAIPEI)
    return taipei.strftime("%H:%M") if taipei.date() == local_date else taipei.strftime("%m-%d %H:%M")


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
    total = sum(sources.values())
    # 來源工作的結果（process_source 回傳的代碼）；failed 是重試完還是失敗的，多半是網站連不上
    changed, unchanged, failed = sources.get("extracted", 0), sources.get("unchanged", 0), sources.get("failed", 0)
    lines = [
        f"{clock(started_at, local_date)} 開始，{clock(finished_at, local_date)} 收尾",
        f"{total} 個來源：有變 {changed}、沒變 {unchanged}、抓不到 {failed}、其他 {total - changed - unchanged - failed}",
        f"這輪產生 {new_events} 則通知",
    ]
    for skipped_day, waited in skipped:
        reason = "沒有單獨檢查：在等前一輪收尾" if waited else "沒有檢查：那天電腦沒開或沒有網路"
        lines.append(f"{day(skipped_day)} {reason}")
    return f"每日檢查完成：{day(local_date)}", lines


def waiting_message(today: date, previous_date: date, previous_started: datetime, now: datetime) -> Message:
    """今天的檢查還沒開始：在等前一輪收尾。"""
    return "", []


def stale_message(previous_date: date, previous_started: datetime, now: datetime) -> Message:
    """前一輪開始太久還沒收尾：可能壞了，今天照常開始。"""
    return "", []
