"""評分規則（docs/spec.md 的「評分」）。"""

from collections.abc import Sequence
from typing import Literal

# 硬性條件的判斷結果：符合、不符合、待確認
CheckResult = Literal["pass", "fail", "unclear"]


def apply_caps(score: float, checks: Sequence[CheckResult]) -> float:
    """依硬性條件的結果套用總分上限：任一不符合最多 20，任一待確認最多 80。"""
    if "fail" in checks:
        return min(score, 20)
    if "unclear" in checks:
        return min(score, 80)
    return score
