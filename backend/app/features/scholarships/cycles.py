"""申請期（cycle）的日期計算：換算成 UTC、算出狀態、推估明年的申請期、決定要不要封存。

用法：uv run python -m app.features.scholarships.cycles（更新狀態、封存、預估下一屆，不呼叫 AI）
"""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.features.scholarships.models import Cycle, Scholarship, ScholarshipStatus
from app.shared.db import SessionLocal

# 申請期的四種狀態：推估的、還沒開放、開放中、已截止
Status = Literal["estimated", "upcoming", "open", "closed"]

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


def cycle_status(opens_at: datetime | None, closes_at: datetime, now: datetime, *, estimated: bool) -> Status:
    """依日期算出申請期現在的狀態；系統推估的申請期一律是 estimated。"""
    if estimated:
        return "estimated"
    if now >= closes_at:
        return "closed"
    if opens_at is not None and now < opens_at:
        return "upcoming"
    return "open"


# 四位數年份，後面可以接「/」或「-」加兩位數年份（例如 2026/27）
YEAR_PATTERN = re.compile(r"(?<!\d)(\d{4})(?!\d)(?:([/-])(\d{2})(?!\d))?")


def _next_year(match: re.Match[str]) -> str:
    text = str(int(match[1]) + 1)
    if match[3]:
        # 兩位數年份：補零，99 的下一年是 00
        text += match[2] + f"{(int(match[3]) + 1) % 100:02d}"
    return text


def next_intake(intake: str | None) -> str | None:
    """入學年度往後推一年（2026/27 → 2027/28）；找不到四位數年份就回傳 None。"""
    if intake is None or not YEAR_PATTERN.search(intake):
        return None
    return YEAR_PATTERN.sub(_next_year, intake)


@dataclass(frozen=True)
class Estimate:
    """推估的明年申請期；recheck_from 是開始回原網站確認真正日期的那一天。"""

    opens_at: datetime | None
    closes_at: datetime
    intake: str | None
    recheck_from: date


def _one_year_later(moment: datetime) -> datetime:
    try:
        return moment.replace(year=moment.year + 1)
    except ValueError:
        # 閏年的 2/29 明年不存在，改成 2/28
        return moment.replace(year=moment.year + 1, day=28)


def estimate_next(opens_at: datetime | None, closes_at: datetime, intake: str | None) -> Estimate:
    """猜明年的申請期：日期都加一年；開放前 30 天（沒寫開放日就截止前 90 天）開始檢查。"""
    next_opens = _one_year_later(opens_at) if opens_at is not None else None
    next_closes = _one_year_later(closes_at)
    if next_opens is not None:
        recheck = next_opens - timedelta(days=30)
    else:
        recheck = next_closes - timedelta(days=90)
    return Estimate(next_opens, next_closes, next_intake(intake), recheck.date())


def estimate_after(opens_at: datetime | None, closes_at: datetime, intake: str | None, today: date) -> Estimate:
    """預估下一屆（ADR-058）：先照 estimate_next 加一年；預估的截止日還在今天以前，就再加一年，直到截止日是今天或以後。"""
    estimate = estimate_next(opens_at, closes_at, intake)
    # 最新資料可能是好幾年前的，加一年還在過去：拿上一次的預估再加一年（入學年度也跟著加）
    while estimate.closes_at.date() < today:
        estimate = estimate_next(estimate.opens_at, estimate.closes_at, estimate.intake)
    return estimate


STALE_AFTER_DAYS = 730  # 最近一次真的截止日超過 24 個月就算資料過舊（ADR-058）


def is_stale(latest_close: datetime, today: date) -> bool:
    """最近一次真的截止日，距離今天超過 730 天就算資料過舊。"""
    # 只比日期：今天減掉截止那天，得到相隔幾天
    return (today - latest_close.date()).days > STALE_AFTER_DAYS


def should_archive(statuses: list[Status]) -> bool:
    """沒有任何申請期還能申請（開放中或即將開放）就封存；一個申請期都沒有時不封存。"""
    return bool(statuses) and not any(status in ("upcoming", "open") for status in statuses)


def refresh(session: Session, now: datetime) -> Counter[str]:
    """更新所有申請期的狀態、封存或喚回獎學金、替封存的獎學金產生預估的下一屆（不呼叫 AI）。"""
    counts: Counter[str] = Counter()
    rows = session.scalars(select(Scholarship).options(selectinload(Scholarship.cycles))).all()
    for row in rows:
        for cycle in row.cycles:
            cycle.status = cycle_status(cycle.opens_at, cycle.closes_at, now, estimated=cycle.estimated)
            counts[cycle.status] += 1
        statuses: list[Status] = [cast(Status, c.status) for c in row.cycles]
        if should_archive(statuses):
            if row.status == ScholarshipStatus.ACTIVE:
                row.status = ScholarshipStatus.ARCHIVED
                counts["archived"] += 1
            if not any(c.estimated for c in row.cycles):
                counts["estimated_new"] += add_estimates(session, row)
        elif row.status == ScholarshipStatus.ARCHIVED:
            row.status = ScholarshipStatus.ACTIVE  # 有開放中或即將開放的申請期：喚回
            counts["recalled"] += 1
    return counts


def add_estimates(session: Session, row: Scholarship) -> int:
    """依最近一屆已截止的申請期，產生下一屆的預估申請期（同一屆有好幾個截止日就各產生一筆）。"""
    closed = [c for c in row.cycles if c.status == "closed"]
    if not closed:
        return 0
    latest = max(closed, key=lambda c: c.closes_at)
    same_intake = [c for c in closed if latest.intake is not None and c.intake == latest.intake] or [latest]
    for cycle in same_intake:
        estimate = estimate_next(cycle.opens_at, cycle.closes_at, cycle.intake)
        session.add(
            Cycle(
                scholarship_id=row.id,
                intake=estimate.intake,
                label=cycle.label,
                opens_at=estimate.opens_at,
                closes_at=estimate.closes_at,
                timezone=cycle.timezone,
                timezone_assumed=cycle.timezone_assumed,
                nationality_scope=cycle.nationality_scope,
                nationalities=cycle.nationalities,
                funding=cycle.funding,
                status="estimated",
                estimated=True,
                recheck_from=estimate.recheck_from,
                evidence=None,  # 預估的沒有原文
            )
        )
    return len(same_intake)


def main() -> None:
    with SessionLocal() as session, session.begin():
        counts = refresh(session, datetime.now(UTC))
    print(
        f"申請期：開放中 {counts['open']}、即將開放 {counts['upcoming']}、"
        f"已截止 {counts['closed']}、預估 {counts['estimated']}"
    )
    print(
        f"這次封存 {counts['archived']} 筆、喚回 {counts['recalled']} 筆、"
        f"新增預估申請期 {counts['estimated_new']} 筆"
    )


if __name__ == "__main__":
    main()
