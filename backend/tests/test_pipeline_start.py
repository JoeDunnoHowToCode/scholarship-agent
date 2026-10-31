"""開始今天的檢查前的判斷（ADR-075）：前一輪還沒收尾，就先不開新的一輪。"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.features.pipeline import jobs
from app.features.pipeline.models import Run

NOW = datetime(2026, 11, 1, 7, 15, tzinfo=UTC)


def run_started(hours_ago: float, finished: bool) -> Run:
    """一輪檢查：幾小時前開始、收尾了沒。"""
    started = NOW - timedelta(hours=hours_ago)
    return Run(
        local_date=date(2026, 10, 31),
        started_at=started,
        finished_at=started + timedelta(hours=1) if finished else None,
    )


@pytest.mark.parametrize(
    ("today_started", "previous", "expected"),
    [
        # 第一次啟用，還沒有任何一輪：不能卡住
        (False, None, "start"),
        # 前一輪已收尾：平常的情況
        (False, run_started(20, finished=True), "start"),
        # 前一輪還沒收尾、開始 10 小時：B 要擋的情況，等它收尾
        (False, run_started(10, finished=False), "wait"),
        # 開始 25 小時還沒收尾：當成收尾壞了（或電腦關機太久），警告後照常開始
        (False, run_started(25, finished=False), "stale"),
        # 剛好 24 小時（邊界）：算太久
        (False, run_started(24, finished=False), "stale"),
        # 今天開始過：原本的規則，不管前一輪
        (True, run_started(10, finished=False), "already_started"),
        # 手動指令不看今天開始過沒（傳 False）：今天那輪已收尾，就可以再排
        (False, run_started(2, finished=True), "start"),
    ],
)
def test_decide_start(today_started: bool, previous: Run | None, expected: str) -> None:
    assert jobs.decide_start(today_started, previous, NOW) == expected
