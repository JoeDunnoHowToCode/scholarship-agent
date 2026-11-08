"""費用摘要（ADR-089）：本月總額、依功能分、最近 7 天每天。指令和紀錄頁共用。"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.features.costs.log import month_total_usd
from app.features.costs.models import LLMCall
from app.features.costs.usage import TAIPEI, month_start

RECENT_DAYS = 7


@dataclass
class Summary:
    month_usd: float = 0.0
    by_feature: list[tuple[str, int, float]] = field(default_factory=list)  # （功能, 次數, 美元），花最多的在前
    by_day: list[tuple[date, float]] = field(default_factory=list)  # （台灣日期, 美元），最近 7 天，舊的在前


def summarize(session: Session, now: datetime) -> Summary:
    by_feature = session.execute(
        select(LLMCall.feature, func.count(), func.sum(LLMCall.cost_usd))
        .where(LLMCall.called_at >= month_start(now))
        .group_by(LLMCall.feature)
        .order_by(func.sum(LLMCall.cost_usd).desc())
    ).tuples().all()
    # 換成台灣時間再取日期：台灣早上 8 點以前的呼叫，UTC 還是前一天
    local_day = cast(func.timezone("Asia/Taipei", LLMCall.called_at), Date)
    first_day = now.astimezone(TAIPEI).date() - timedelta(days=RECENT_DAYS - 1)
    by_day = session.execute(
        select(local_day, func.sum(LLMCall.cost_usd))
        .where(local_day >= first_day)
        .group_by(local_day)
        .order_by(local_day)
    ).tuples().all()
    return Summary(
        month_usd=month_total_usd(session, now),
        by_feature=[(name, int(count), float(usd or 0)) for name, count, usd in by_feature],
        by_day=[(day, float(usd or 0)) for day, usd in by_day],
    )
