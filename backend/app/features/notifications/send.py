"""送出待送的通知（第 8 天，ADR-062）：讀 events 表裡待送的，超過 5 則合併成摘要，經插座送出，再標記已送。

用法：uv run python -m app.features.notifications.send             馬上送出
      uv run python -m app.features.notifications.send --preview   只預覽、不送

至少送一次：送出之後、標記已送之前當掉的話，下次會再送一次那一則。
"""

import argparse
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.notify.base import Notification, Notifier
from app.core.notify.telegram import notifier_from_settings, to_html
from app.core.notify.telegram_api import TelegramError
from app.features.notifications.models import Event
from app.features.notifications.rules import bundle
from app.features.profiles.service import CURRENT_USER_ID
from app.shared.db import SessionLocal


def to_notification(event: Event) -> Notification:
    payload = event.payload
    return Notification(
        kind=payload["kind"], title=payload["title"], lines=tuple(payload["lines"]), url=payload["url"]
    )


def outgoing(events: list[Event]) -> list[tuple[Notification, list[Event]]]:
    """要送出的訊息，以及每則訊息包含哪些事件：系統事件各自一則；其他超過 5 則就合成一則摘要。"""
    system = [(to_notification(e), [e]) for e in events if e.kind == "system"]
    others = [e for e in events if e.kind != "system"]
    merged = bundle([to_notification(e) for e in others])
    if len(merged) == 1 and len(others) > 1:
        return system + [(merged[0], others)]  # 合併成一則摘要，包含全部事件
    return system + [(to_notification(e), [e]) for e in others]


def pending(session: Session, user_id: int) -> list[Event]:
    return list(
        session.scalars(
            select(Event).where(Event.user_id == user_id, Event.status == "pending").order_by(Event.id)
        )
    )


def send_pending(session: Session, notifier: Notifier, user_id: int, now: datetime) -> dict[str, int]:
    """一則一則送；每送成功一則就標記已送並 commit。格式錯（400）記成失敗；其他錯誤先停下、保持待送。"""
    counts: Counter[str] = Counter()
    for message, group in outgoing(pending(session, user_id)):
        try:
            notifier.send(message)
        except TelegramError as error:
            for event in group:
                event.attempts += 1
                event.last_error = str(error)
            if error.code == 400:  # 這則的內容 Telegram 不收：記成失敗，不再重送
                for event in group:
                    event.status = "failed"
                session.commit()
                counts["failed"] += len(group)
                continue
            session.commit()
            raise  # token、聊天設定或限速出問題：先停下，剩下的保持待送，交給 RQ 稍後重試
        for event in group:
            event.status = "sent"
            event.sent_at = now
            event.attempts += 1
        session.commit()
        counts["messages"] += 1
        counts["sent"] += len(group)
    return dict(counts)


def send_events() -> dict[str, int] | str:
    """RQ 工作：送出待送的通知（每天收尾後、斷路器打開時各放一件）。"""
    try:
        notifier = notifier_from_settings()
    except TelegramError as error:
        return f"還不能送：{error}"  # 還沒設定聊天 ID：事件留著，設定好之後下一次再送
    with SessionLocal() as session:
        return send_pending(session, notifier, CURRENT_USER_ID, datetime.now(UTC))


def main() -> None:
    parser = argparse.ArgumentParser(description="送出待送的通知（或只預覽）")
    parser.add_argument("--preview", action="store_true", help="只印出會送的訊息，不送")
    args = parser.parse_args()
    if args.preview:
        with SessionLocal() as session:
            messages = outgoing(pending(session, CURRENT_USER_ID))
        print(f"待送的訊息 {len(messages)} 則：")
        for message, group in messages:
            print(f"--- {message.kind}（包含 {len(group)} 個事件）\n{to_html(message)}")
        return
    print(send_events())


if __name__ == "__main__":
    main()
