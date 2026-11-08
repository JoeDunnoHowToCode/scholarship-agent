"""費用摘要（ADR-089）：本月總額、依功能分、最近 7 天每天。指令和紀錄頁共用。"""

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.orm import Session


@dataclass
class Summary:
    month_usd: float = 0.0
    by_feature: list[tuple[str, int, float]] = field(default_factory=list)  # （功能, 次數, 美元），花最多的在前
    by_day: list[tuple[date, float]] = field(default_factory=list)  # （台灣日期, 美元），最近 7 天，舊的在前


def summarize(session: Session, now: datetime) -> Summary:
    return Summary()  # 骨架
