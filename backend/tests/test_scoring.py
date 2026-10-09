"""評分上限規則的單元測試（docs/spec.md「評分」第 1 點、ADR-022）。"""

import pytest

from app.features.matching import scoring


def test_unclear_caps_at_80() -> None:
    # 有任何一項「待確認」，總分最多 80
    assert scoring.apply_caps(95, ["pass", "unclear"]) == 80


def test_fail_caps_at_20_over_unclear() -> None:
    # 有任何一項「不符合」，總分最多 20，而且比「待確認」優先
    assert scoring.apply_caps(95, ["fail", "unclear"]) == 20


@pytest.mark.parametrize("checks", [["pass", "pass"], []])
def test_all_pass_keeps_score(checks: list[scoring.CheckResult]) -> None:
    # 全部符合，或沒有任何檢查項目：分數不變
    assert scoring.apply_caps(95, checks) == 95
