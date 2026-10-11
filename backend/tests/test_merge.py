"""長文件合併規則的單元測試（ADR-034、docs/day-03.md「Claude 自行決定」第 9 點）。"""

from typing import Any

from app.features.scholarships import merge
from app.features.scholarships.schemas import Outline, SectionFacts

EMPTY: dict[str, Any] = {
    "provider": None,
    "countries": [],
    "degrees": [],
    "degrees_evidence": None,
    "fields": [],
    "coverage": None,
    "amount": None,
    "taiwan_eligibility": "unclear",
    "taiwan_evidence": None,
    "nationality_scope": "unclear",
    "nationality_evidence": None,
    "taiwan_conditions": None,
    "language_requirements": None,
    "other_eligibility": None,
    "requires_admission": None,
    "intake": None,
    "deadline": None,
    "deadline_timezone": None,
    "deadline_evidence": None,
    "category_facts": [],
    "requirements": [],
}


def section(**fields: Any) -> SectionFacts:
    # 一節裡沒提到的欄位都是空的，測試只寫出這一節有提到的
    return SectionFacts(**{**EMPTY, **fields})


OUTLINE = Outline(name="GSSA", name_zh="留學獎學金", provider="教育部", category_names=[])


def test_first_value_wins_and_a_different_value_is_a_conflict() -> None:
    # 截止日取第一個有值的；後面出現不同的值，記成衝突，交給驗證者標待確認
    result = merge.merge_sections(
        OUTLINE,
        [
            section(),
            section(deadline="2027-02-13", deadline_evidence="2 月 13 日截止"),
            section(deadline="2027-03-16", deadline_evidence="3 月 16 日截止"),
        ],
    )
    assert result.draft.deadline == "2027-02-13"
    assert result.draft.deadline_evidence == "2 月 13 日截止"
    assert result.conflicts == ["deadline"]


def test_lists_are_unioned_and_texts_are_joined() -> None:
    # 清單欄位取聯集（保持出現順序）；文字欄位把不同的內容串起來，不算衝突
    result = merge.merge_sections(
        OUTLINE,
        [
            section(countries=["Denmark", "Sweden"], degrees=["phd"], coverage="學費"),
            section(countries=["Sweden", "Norway"], degrees=["master", "phd"], coverage="生活費"),
            section(coverage="學費"),
        ],
    )
    assert result.draft.countries == ["Denmark", "Sweden", "Norway"]
    assert result.draft.degrees == ["phd", "master"]
    assert result.draft.coverage == "學費\n生活費"
    assert result.conflicts == []
