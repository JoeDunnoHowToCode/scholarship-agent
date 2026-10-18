"""申請期（cycle）的日期計算：換算成 UTC、算出狀態、推估明年的申請期、決定要不要封存。"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def to_utc(year: int, month: int, day: int, time: str | None, timezone: str | None) -> tuple[datetime, bool]:
    """把原文的當地日期時間換成 UTC；第二個值表示時區是不是我們假設的。"""
    hour, minute = (int(part) for part in (time or "").split(":"))
    local = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone or ""))
    return local.astimezone(UTC), False
