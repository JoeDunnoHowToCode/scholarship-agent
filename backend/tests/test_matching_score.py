"""評分指令的單元測試（第 6 天）。"""

import pytest
from pydantic import ValidationError

from app.features.matching import score


def test_sub_score_requires_a_number() -> None:
    # AI 回傳空白分數時，加權總分會跳過這一項、用其他項放大，等於把「不知道」當成「和其他項一樣好」；
    # 第 6 天重新評分時，領域不合的學程因為領域分數空白排到第 4 名。所以 AI 給的分數一定要是數字
    with pytest.raises(ValidationError):
        score.SubScore(score=None, reason="原文沒寫")
