"""網頁列表的純函式（第 9 天）：排序與分組，不碰資料庫，方便單元測試。"""

# 時間狀態的順序（ADR-059）：還能申請 → 時間待確認 → 已截止或不適用
GROUP_ORDER = {"pass": 0, "unclear": 1, "fail": 2}


def list_order(group: str | None, score: float | None) -> tuple[int, float]:
    """列表的排序鍵：先依時間狀態分組，同組依分數由高到低；還沒評分的（沒有時間狀態）排最後。"""
    rank = GROUP_ORDER[group] if group in GROUP_ORDER else len(GROUP_ORDER)
    return rank, -(score or 0.0)
