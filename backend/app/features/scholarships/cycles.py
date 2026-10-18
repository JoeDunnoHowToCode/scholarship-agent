"""申請期（cycle）的日期計算：換算成 UTC、算出狀態、推估明年的申請期、決定要不要封存。"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# 24 小時制的 "HH:MM"：小時 00–23，分鐘 00–59
TIME_PATTERN = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")
# UTC+14（吉里巴斯）；Etc/ 開頭的時區正負號是反的，所以寫成 GMT-14
EARLIEST_ZONE = ZoneInfo("Etc/GMT-14")


def to_utc(year: int, month: int, day: int, time: str | None, timezone: str | None) -> tuple[datetime, bool]:
    """把原文的當地日期時間換成 UTC；第二個值表示時區是不是我們假設的。"""
    # 沒寫時間或寫錯，就當成當天最後一分鐘 23:59（截止日通常指當天結束前）
    match = TIME_PATTERN.fullmatch(time or "")
    hour, minute = (int(match[1]), int(match[2])) if match else (23, 59)
    # 沒寫時區或時區名稱不存在，就用全世界最早過完這一天的 UTC+14：寧可算早，也不要讓使用者以為還來得及
    try:
        zone, assumed = ZoneInfo(timezone or ""), False
    except (ZoneInfoNotFoundError, ValueError):
        zone, assumed = EARLIEST_ZONE, True
    local = datetime(year, month, day, hour, minute, tzinfo=zone)
    return local.astimezone(UTC), assumed
