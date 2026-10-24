"""斷路器（ADR-056）：Gemini 額度用完、金鑰或模型設定有問題、或費用超過上限時打開，暫停所有 AI 步驟。

用法：uv run python -m app.features.pipeline.breaker              看目前的狀態
      uv run python -m app.features.pipeline.breaker --reset      處理好之後恢復
      uv run python -m app.features.pipeline.breaker --open 原因   手動打開（例如想暫停 AI）
"""

import argparse
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.pipeline.models import Breaker
from app.shared.db import SessionLocal

AI = "ai"  # 目前只有一個斷路器：管所有用到 Gemini 的步驟


def get(session: Session) -> Breaker | None:
    return session.scalars(select(Breaker).where(Breaker.name == AI)).first()


def is_open(session: Session) -> bool:
    row = get(session)
    return row is not None and row.opened_at is not None


def open_breaker(session: Session, reason: str) -> None:
    """打開斷路器；已經打開的話，保留第一次的原因與時間（那才是根本原因）。"""
    row = get(session) or Breaker(name=AI)
    if row.opened_at is None:
        row.opened_at = datetime.now(UTC)
        row.reason = reason
    session.add(row)


def reset(session: Session) -> None:
    row = get(session)
    if row is not None:
        row.opened_at = None
        row.reason = None


def main() -> None:
    parser = argparse.ArgumentParser(description="看、打開或恢復 AI 的斷路器（ADR-056）")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--reset", action="store_true", help="處理好之後恢復 AI 步驟")
    action.add_argument("--open", metavar="原因", help="手動打開，暫停 AI 步驟")
    args = parser.parse_args()
    with SessionLocal() as session, session.begin():
        if args.reset:
            reset(session)
        elif args.open:
            open_breaker(session, args.open)
    with SessionLocal() as session:
        if args.open:
            # 在這裡才 import：jobs 也會 import 這個檔案，放在最上面會互相 import
            from app.features.pipeline.jobs import notify_breaker

            notify_breaker(session)  # 斷路器打開了：通知你（會自己 commit）
        row = get(session)
        if row is None or row.opened_at is None:
            print("斷路器關著：AI 步驟照常執行")
        else:
            print(f"斷路器打開中（{row.opened_at:%Y-%m-%d %H:%M} UTC）：{row.reason}")


if __name__ == "__main__":
    main()
