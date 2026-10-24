"""產生通知事件（第 8 天，ADR-062）：從資料庫裡已經存好的資料算出要通知的事，寫進 events 表（Outbox）。

- 每個事件有唯一的去重鍵，重跑不會重複產生
- 第一次啟用時，現有的新獎學金、新年度與變更只記成 baseline、不送；截止提醒照送
- 只通知適配度達門檻的獎學金（ADR-059、060）；內容不放提到科系的理由（ADR-063）
"""

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.features.matching.models import Match
from app.features.matching.score import describe_cycle, possible_cycles
from app.features.notifications.models import Event
from app.features.notifications.rules import (
    REMINDER_DAYS,
    cycle_year,
    describe_change,
    reminder_bucket,
)
from app.features.profiles.service import get_profile
from app.features.scholarships.models import Change, Cycle, Scholarship
from app.shared.settings import settings

TAIPEI = ZoneInfo("Asia/Taipei")
CHANGE_WINDOW_DAYS = 14  # 只看最近 14 天的變更紀錄；更早的已經處理過


def best_scores(session: Session, user_id: int) -> dict[int, float]:
    """每筆獎學金分數最高的類別（一筆獎學金常有好幾個類別）。"""
    rows = session.execute(
        select(Match.scholarship_id, func.max(Match.total))
        .where(Match.user_id == user_id)
        .group_by(Match.scholarship_id)
    ).all()
    return {scholarship_id: float(total) for scholarship_id, total in rows}


def closing_date(cycle: Cycle) -> date:
    """截止日用申請期原本時區的日期；時區是假設的就用 UTC 的日期（和 describe_cycle 一致）。"""
    if cycle.timezone and not cycle.timezone_assumed:
        return cycle.closes_at.astimezone(ZoneInfo(cycle.timezone)).date()
    return cycle.closes_at.date()


def note(kind: str, title: str, lines: list[str], url: str | None) -> dict[str, Any]:
    """events.payload：結構化通知（ADR-063），送出時換成 Notification。"""
    return {"kind": kind, "title": title, "lines": lines, "url": url}


class EventWriter:
    """寫事件：去重鍵已經有了就跳過；第一次啟用時，非截止提醒的事件記成 baseline。"""

    def __init__(self, session: Session, user_id: int, now: datetime) -> None:
        self.session, self.user_id, self.now = session, user_id, now
        self.first_time = not session.scalar(select(exists().where(Event.user_id == user_id)))
        self.known = set(session.scalars(select(Event.dedup_key).where(Event.user_id == user_id)))
        self.counts: Counter[str] = Counter()

    def add(self, kind: str, key: str, scholarship_id: int | None, payload: dict[str, Any], baseline: bool) -> bool:
        """新增一個事件；回傳有沒有真的新增成「待送」。"""
        if key in self.known:
            return False
        self.known.add(key)
        status = "baseline" if baseline else "pending"
        self.session.add(
            Event(
                user_id=self.user_id, kind=kind, scholarship_id=scholarship_id, dedup_key=key,
                payload=payload, status=status, created_at=self.now,
            )
        )
        self.counts[f"{kind}:{status}"] += 1
        return status == "pending"


def generate(session: Session, user_id: int, now: datetime) -> dict[str, int]:
    """依 docs/day-08.md「Claude 自行決定」第 2–8 點產生事件；呼叫的人負責 commit。"""
    profile = get_profile(session, user_id)
    if profile is None:
        return {"no_profile": 1}
    today = now.astimezone(TAIPEI).date()
    writer = EventWriter(session, user_id, now)
    scores = best_scores(session, user_id)
    threshold = settings.notify_threshold
    rows = session.scalars(
        select(Scholarship)
        .where(Scholarship.duplicate_of.is_(None), Scholarship.source_id.is_not(None))
        .options(selectinload(Scholarship.cycles))
        .order_by(Scholarship.id)
    ).all()
    for row in rows:
        score = scores.get(row.id)
        if score is None or score < threshold:
            continue
        label = f"{row.name}（{score:.0f} 分）"
        # 還有機會申請、可能適用你、不是預估的申請期（第 7 天的 still_possible）
        cycles = [c for c in possible_cycles(list(row.cycles), profile.nationality) if not c.estimated]
        first_line = [describe_cycle(cycles[0])] if cycles else []
        fresh = writer.add(
            "new_scholarship", f"new:{row.id}", row.id,
            note("new_scholarship", f"新獎學金：{label}", first_line, row.official_url), writer.first_time,
        )
        for cycle in cycles:
            closing = closing_date(cycle)
            # 新年度開放：同一筆獎學金每一屆只通知一次（同一屆的截止日被更正，交給「資料變更」）；
            # 剛通知過「新獎學金」的，這次就不再另外通知
            writer.add(
                "new_cycle", f"cycle:{row.id}:{cycle_year(cycle.intake, closing.year)}", row.id,
                note("new_cycle", f"新年度開放：{label}｜截止 {closing}", [describe_cycle(cycle)], row.official_url),
                writer.first_time or fresh,
            )
            days_left = (closing - today).days
            sent = {days for days in REMINDER_DAYS if f"deadline:{row.id}:{closing}:{days}" in writer.known}
            bucket = reminder_bucket(days_left, sent)
            if bucket is not None:
                when = "今天截止" if days_left == 0 else f"還剩 {days_left} 天"
                writer.add(
                    "deadline", f"deadline:{row.id}:{closing}:{bucket}", row.id,
                    note("deadline", f"截止提醒：{row.name} {when}", [describe_cycle(cycle)], row.official_url),
                    False,  # 截止提醒是現在的事，第一次啟用也照送
                )
    since = now - timedelta(days=CHANGE_WINDOW_DAYS)
    by_id = {row.id: row for row in rows}
    for change in session.scalars(select(Change).where(Change.changed_at >= since).order_by(Change.id)):
        score = scores.get(change.scholarship_id)
        changed = by_id.get(change.scholarship_id)
        if changed is None or score is None or score < threshold:
            continue
        text = describe_change(change.field, change.old_value, change.new_value, today=today)
        if text is not None:
            # 標題直接帶變更內容：合併成摘要時只列標題，也看得懂變了什麼
            writer.add(
                "change", f"change:{change.id}", changed.id,
                note("change", f"資料變更：{changed.name}｜{text}", [], changed.official_url), writer.first_time,
            )
    return dict(writer.counts)


def add_system_event(session: Session, user_id: int, key: str, title: str, lines: list[str], now: datetime) -> None:
    """系統事件（例如斷路器打開）：不看門檻、不建基準線；呼叫的人負責 commit。"""
    writer = EventWriter(session, user_id, now)
    writer.add("system", key, None, note("system", title, lines, None), False)
