"""評分上限規則的單元測試（docs/spec.md「評分」第 1 點、ADR-022）。"""

from app.features.matching import scoring


def test_unclear_caps_at_80() -> None:
    # 有任何一項「待確認」，總分最多 80
    assert scoring.apply_caps(95, ["pass", "unclear"]) == 80
