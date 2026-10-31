"""馬上開始一次檢查（第 7 天，ADR-057）：不等 tick，也不管今天開始過沒；但前一輪還沒收尾就不排（ADR-075）。

用法：uv run python -m app.features.pipeline.run [--source ID …]

不給 --source 就檢查今天到期的全部來源。工作放進佇列，由 worker 執行
（uv run rq worker -w rq.worker.SpawnWorker --with-scheduler）。
"""

import argparse
from datetime import UTC, datetime

from sqlalchemy import select

from app.features.pipeline.jobs import (
    decide_start,
    due_source_ids,
    latest_run,
    start_run,
    taipei_date,
    warn_stale,
)
from app.features.pipeline.models import Run
from app.shared.db import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="馬上開始一次檢查（放進佇列，由 worker 執行）")
    parser.add_argument("--source", type=int, action="append", default=[], help="只檢查這個來源 id，可以給好幾次")
    args = parser.parse_args()
    today = taipei_date()
    now = datetime.now(UTC)
    with SessionLocal() as session:
        # 手動指令也遵守「前一輪還沒收尾就不開」，否則一樣會疊在一起、通知被擋住（使用者 10-31 決定）
        previous = latest_run(session)
        step = decide_start(False, previous, now)
        if step == "wait":
            assert previous is not None  # decide_start 只有在有前一輪時才會回 wait、stale
            print(f"前一輪（{previous.local_date}）還沒收尾，等它收尾再跑")
            return
        if step == "stale":
            assert previous is not None
            warn_stale(session, previous, now)
        run = session.scalars(select(Run).where(Run.local_date == today)).first()
        if run is None:
            run = Run(local_date=today, started_at=datetime.now(UTC))
            session.add(run)
            session.commit()
        source_ids = args.source or due_source_ids(session, today)
        start_run(session, run, source_ids)
    print(f"已放進佇列：{len(source_ids)} 個來源，加上一件收尾工作")


if __name__ == "__main__":
    main()
