"""網頁列表的純函式（第 9 天）：排序與分組，不碰資料庫，方便單元測試。"""

from app.features.matching.score import possible_cycles
from app.features.scholarships.models import Cycle

# 時間狀態的順序（ADR-059）：還能申請 → 時間待確認 → 已截止或不適用
GROUP_ORDER = {"pass": 0, "unclear": 1, "fail": 2}


def list_order(group: str | None, score: float | None) -> tuple[int, float]:
    """列表的排序鍵：先依時間狀態分組，同組依分數由高到低；還沒評分的（沒有時間狀態）排最後。"""
    rank = GROUP_ORDER[group] if group in GROUP_ORDER else len(GROUP_ORDER)
    return rank, -(score or 0.0)


def card_cycle(cycles: list[Cycle], nationality: str | None) -> Cycle | None:
    """列表卡片上「截止日期」那一行要顯示的申請期（ADR-077，11-04 修改）。

    有國籍時，挑還能申請、國籍符合或待確認的申請期裡截止最早的一輪；沒填個人資料、或沒有適用的，
    就挑所有還沒截止、給申請獎學金的人的申請期裡最早的一輪；都截止了就沒有。
    """
    if nationality:
        mine = possible_cycles(cycles, nationality)
        if mine:
            return mine[0]
    still_open = [c for c in cycles if c.status != "closed" and c.funding in ("scholarship", "any")]
    return min(still_open, key=lambda c: c.closes_at, default=None)
