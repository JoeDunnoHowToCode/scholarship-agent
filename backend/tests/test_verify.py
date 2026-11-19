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
        "coverage": None, "amounts": [], "nationality_scope": "unclear", "nationalities": [],
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


def test_a_window_that_closes_before_it_opens_is_flagged() -> None:
    # 總檢查的例子：開放 2026 年 10 月、截止卻是 2007 年 1 月；不用問 AI 就知道不對
    window = WindowDraft(label=None, intake=None, opens_year=2026, opens_month=10, opens_day=1,
                         closes_year=2007, closes_month=1, closes_day=15, closes_time=None, timezone=None,
                         nationality_scope="all", nationalities=[], funding="any",
                         evidence="Applications open 1 October 2026 and close 15 January 2007")
    source = "Applications open 1 October 2026 and close 15 January 2007."
    scholarship = draft([], None).model_copy(update={"degrees": [], "windows": [window]})
    assert verify.verify(NoCallLLM(), scholarship, source, [])["deadlines"] == ["closes_before_opens"]


def test_eu_countries_excluded_as_a_group_are_not_flagged_one_by_one() -> None:
    # 原文寫「只限非歐盟／EEA 學生」，AI 照提示詞列出被排除的歐盟各國：原文本來就不會寫出每個國名，不算問題
    scholarship = draft([], None).model_copy(update={
        "nationality_scope": "excluded", "nationalities": ["AT", "FR", "NO", "CH", "JP"],
        "nationality_evidence": "The scholarship is only for non-EU/EEA students.",
    })
    source = "The scholarship is only for non-EU/EEA students."
    assert verify.other_issues(scholarship, source) == ["nationality_not_in_source:JP"]  # 日本不在歐盟，照樣要在原文找得到


def test_the_nationality_claim_names_the_country_groups() -> None:
    # ADR-109：AI 填群組代號時國家清單是空的；核對的 AI 要看到群組，才能判斷引用支不支持
    groups_draft = draft([], None).model_copy(update={
        "nationality_scope": "listed", "nationalities": ["CH"], "nationality_groups": ["EU"],
        "nationality_evidence": "EU and Swiss citizens",
    })
    assert verify.claims(groups_draft)["nationality"] == ("listed CH, EU", "EU and Swiss citizens")


def test_not_scholarship_is_judged_by_the_ai_check_too() -> None:
    # A2 C（ADR-107）：11-16 重抽時，引用在原文裡卻判錯的有好幾個（只說這一屆沒有、講的是學費）；
    # 「不是獎學金」也交給核對的 AI：引用要撐得起「完全不提供任何獎學金，不是只有這一屆沒有」
    from app.features.scholarships.verify import ClaimVerdict, Verdicts

    quote = "This edition will be self-funded only"

    class Judge:
        def extract(self, prompt: str, schema: type[Any]) -> Any:
            claims = [line[2:].split("：")[0] for line in prompt.splitlines() if line.startswith("- ")]
            return Verdicts(verdicts=[ClaimVerdict(claim=c, supported=c != "not_scholarship", reason="")
                                      for c in claims])

    flagged = draft([], None).model_copy(update={"not_scholarship": True, "not_scholarship_evidence": quote})
    status = verify.verify(Judge(), flagged, f"Intro. {quote}. More.", [])  # type: ignore[arg-type]
    assert status["not_scholarship"] == "not_supported"
    assert "not_scholarship" not in verify.verify(Judge(), draft([], None), quote, [])  # type: ignore[arg-type]


def test_offered_yes_or_no_is_checked_and_becomes_unclear_when_not_supported() -> None:
    # ADR-111：「今年有沒有開」也交給核對的 AI；引用撐不起就改成 unclear（標準 5.1：不確定就是 unclear）
    from app.features.scholarships.verify import ClaimVerdict, Verdicts

    quote = "Applications for the 2026 intake are closed"

    class Judge:
        def extract(self, prompt: str, schema: type[Any]) -> Any:
            claims = [line[2:].split("：")[0] for line in prompt.splitlines() if line.startswith("- ")]
            return Verdicts(verdicts=[ClaimVerdict(claim=c, supported=c != "offered", reason="") for c in claims])

    said_yes = draft([], None).model_copy(update={"offered": "yes", "offered_evidence": quote})
    status = verify.verify(Judge(), said_yes, f"News. {quote}. More.", [])  # type: ignore[arg-type]
    assert status["offered"] == "not_supported"
    assert verify.apply_verification(said_yes, status).offered == "unclear"
    # unclear 本來就不核對
    assert "offered" not in verify.verify(Judge(), draft([], None), quote, [])  # type: ignore[arg-type]


def test_how_to_apply_is_checked_and_becomes_unclear_when_not_supported() -> None:
    # ADR-119：「申請方式」取代意思不清的「要先錄取」；和今年有沒有開一樣，引用撐不起就改成 unclear
    from app.features.scholarships.verify import ClaimVerdict, Verdicts

    quote = "There is no need to apply. You will automatically receive the scholarship if you enrol"

    class Judge:
        def extract(self, prompt: str, schema: type[Any]) -> Any:
            claims = [line[2:].split("：")[0] for line in prompt.splitlines() if line.startswith("- ")]
            return Verdicts(verdicts=[ClaimVerdict(claim=c, supported=c != "how_to_apply", reason="") for c in claims])

    automatic = draft([], None).model_copy(update={"how_to_apply": "automatic", "how_to_apply_evidence": quote})
    status = verify.verify(Judge(), automatic, f"Fees. {quote}. More.", [])  # type: ignore[arg-type]
    assert status.get("how_to_apply") == "not_supported"
    assert verify.apply_verification(automatic, status).how_to_apply == "unclear"
