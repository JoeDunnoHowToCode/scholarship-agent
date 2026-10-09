"""評分規則（docs/spec.md 的「評分」）。"""

from collections.abc import Sequence
from typing import Literal

# 硬性條件的判斷結果：符合、不符合、待確認
CheckResult = Literal["pass", "fail", "unclear"]


def apply_caps(score: float, checks: Sequence[CheckResult]) -> float:
    if "fail" in checks:
        return 20
    return 80
