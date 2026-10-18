"""申請期（cycle）的日期計算：換算成 UTC、算出狀態、推估明年的申請期、決定要不要封存。"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

# 24 小時制的 "HH:MM"：小時 00–23，分鐘 00–59
TIME_PATTERN = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def to_utc(year: int, month: int, day: int, time: str | None, timezone: str | None) -> tuple[datetime, bool]:
    """把原文的當地日期時間換成 UTC；第二個值表示時區是不是我們假設的。"""
    # 沒寫時間或寫錯，就當成當天最後一分鐘 23:59（寧可晚，不要提早說截止了）
    match = TIME_PATTERN.fullmatch(time or "")
    hour, minute = (int(match[1]), int(match[2])) if match else (23, 59)
    local = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone or ""))
    return local.astimezone(UTC), False
