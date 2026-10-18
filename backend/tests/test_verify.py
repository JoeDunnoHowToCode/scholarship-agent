"""驗證者裡純程式檢查的單元測試（ADR-045、046）。"""

from typing import Any

from app.features.scholarships import verify
from app.features.scholarships.schemas import (
    CategoryDraft,
    ScholarshipDraft,
    WindowDraft,
)

SOURCE = "一般生一律以攻讀博士學位為限。(1)北歐國家：10 名。新南向國家者，得攻讀碩士或博士學位：15 名。"


def category(name: str, degrees: list[str], degrees_evidence: str | None) -> CategoryDraft:
    return CategoryDraft(
        name=name, quota=None, degrees=degrees, countries=[], amount=None,  # type: ignore[arg-type]
        eligibility=None, quota_evidence=None, degrees_evidence=degrees_evidence,
        degree_conditions=None,
    )


def draft(categories: list[CategoryDraft], degrees_evidence: str | None) -> ScholarshipDraft:
    empty: dict[str, Any] = {
        "provider": None, "countries": [], "degrees": ["master", "phd"], "fields": [],
        "coverage": None, "amount": None, "nationality_scope": "unclear", "nationalities": [],
        "nationality_evidence": None, "nationality_conditions": None,
        "language_requirements": None, "other_eligibility": None, "requires_admission": None,
    "total_quota": None, "windows": [],
        "name_zh": None, "requirements": [],
    }
    return ScholarshipDraft(
        name="GSSA", categories=categories, degrees_evidence=degrees_evidence, **empty
    )


def test_each_category_needs_its_own_degree_quote() -> None:
    # 教育部北歐的真實情況：學位填了碩士，但北歐自己的學位引用只寫博士；
    # 整份簡章另一句「得攻讀碩士或博士學位」是講新南向的，不能拿來替北歐背書（ADR-046）
    nordic = category("北歐國家", ["master", "phd"], "一般生一律以攻讀博士學位為限")
    south = category("新南向國家", ["master", "phd"], "新南向國家者，得攻讀碩士或博士學位")
    issues = verify.category_issues(draft([nordic, south], "得攻讀碩士或博士學位"), SOURCE)
    assert issues.get("北歐國家") == ["degree_not_in_quote:master"]
    assert "新南向國家" not in issues


def test_single_category_may_use_the_program_degree_quote() -> None:
    # 只有一個類別時，類別就是整個獎學金，可以用整個獎學金的學位引用
    only = category("GSSA", ["master", "phd"], None)
    assert verify.category_issues(draft([only], "得攻讀碩士或博士學位"), SOURCE + "GSSA") == {}


class NoCallLLM:
    """這個測試不該呼叫 AI：所有窗口都在程式檢查那一關就決定了。"""

    def extract(self, prompt: str, schema: type[Any]) -> Any:
        raise AssertionError("不應該呼叫 AI")


def test_each_window_year_and_quote_are_checked_on_their_own() -> None:
    # ADR-047：每個截止日各自核對。學程 82 的真實例子：原文只寫「1st of March」，
    # 模型卻補了年份 → 年份不在引用裡；引用在原文找不到 → 引用不存在；只有月份 → 日期不完整
    windows = [
        WindowDraft(label=None, intake=None, opens_year=None, opens_month=None, opens_day=None,
                    closes_year=2025, closes_month=3, closes_day=1, closes_time=None, timezone=None,
                    nationality_scope="all", nationalities=[], funding="any",
                    evidence="1st of March: All nationals applying"),
        WindowDraft(label=None, intake=None, opens_year=None, opens_month=None, opens_day=None,
                    closes_year=2027, closes_month=2, closes_day=28, closes_time=None, timezone=None,
                    nationality_scope="all", nationalities=[], funding="any",
                    evidence="Deadline: 28 February 2027"),
        WindowDraft(label=None, intake=None, opens_year=None, opens_month=None, opens_day=None,
                    closes_year=None, closes_month=2, closes_day=None, closes_time=None, timezone=None,
                    nationality_scope="all", nationalities=[], funding="any",
                    evidence="Mid-February: Scholarship application deadline"),
    ]
    source = "1st of March: All nationals applying. Mid-February: Scholarship application deadline"
    scholarship = draft([], None).model_copy(update={"degrees": [], "windows": windows})
    result = verify.verify(NoCallLLM(), scholarship, source, [])
    assert result["deadlines"] == ["year_not_in_quote", "quote_not_found", "incomplete"]
