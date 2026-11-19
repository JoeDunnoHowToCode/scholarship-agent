"""評分指令的單元測試（第 6 天）。"""

import pytest
from pydantic import ValidationError

from app.features.matching import score


def test_sub_score_requires_a_number() -> None:
    # AI 回傳空白分數時，加權總分會跳過這一項、用其他項放大，等於把「不知道」當成「和其他項一樣好」；
    # 第 6 天重新評分時，領域不合的學程因為領域分數空白排到第 4 名。所以 AI 給的分數一定要是數字
    with pytest.raises(ValidationError):
        score.SubScore(score=None, reason="原文沒寫")


def test_a_regional_quota_category_is_judged_by_its_own_region() -> None:
    # ADR-112：MULTICOM 的地區名額存成類別。整個獎學金開放所有國籍，但「Sub-Saharan Africa」那一類只給非洲；
    # Asia 那一類官方把台灣列在「高所得國家與地區」，地區名額不一定給，算待確認
    from datetime import UTC, datetime

    from app.features.profiles.models import Profile
    from app.features.scholarships.models import Scholarship

    profile = Profile(user_id=990003, nationality="TW", target_degree="master", target_fields=[],
                      target_countries=[], version=1, updated_at=datetime.now(UTC))
    row = Scholarship(name="Test regional quotas", nationality_scope="all", nationalities=[], extracted={})
    regular = {"name": "Erasmus Mundus scholarship", "degrees": ["master"]}
    africa = {"name": "Sub-Saharan Africa", "degrees": ["master"], "nationality_groups": ["SUB_SAHARAN_AFRICA"]}
    asia = {"name": "Asia", "degrees": ["master"], "nationality_groups": ["ASIA"]}
    results = [score.hard_checks(profile, row, category, [])["nationality"][0] for category in (regular, africa, asia)]
    assert results == ["pass", "fail", "unclear"]
