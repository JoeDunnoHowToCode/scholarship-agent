"""天天抓不到的來源（ADR-080）：連續 3 天都失敗就標記並通知你，之後每 7 天再試一次，恢復了就通知你。"""

from datetime import date
from typing import Literal

# 失敗幾天（不同的日子才算）就標記成抓不到
UNREACHABLE_AFTER_DAYS = 3

# 這次要不要通知：標記成抓不到、恢復了、不用通知
Notice = Literal["unreachable", "recovered"] | None

# 來源的失敗狀態：失敗了幾天、最後一次失敗的日期、從哪天起標記成抓不到
State = tuple[int, date | None, date | None]


def next_state(state: State, failed: bool, today: date) -> tuple[State, Notice]:
    """這一輪的結果出來後，來源新的失敗狀態，以及要不要通知。"""
    return state, None
