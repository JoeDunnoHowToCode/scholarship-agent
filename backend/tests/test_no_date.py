"""沒有申請期的原因由程式決定（ADR-119，總檢查 C1）：依抽取結果找出第一個符合的原因，網頁照實寫出來。"""

from typing import Any

import pytest

from app.features.scholarships import cycles


def window(kind: str = "scholarship", **dates: int | None) -> dict[str, Any]:
    base = {"kind": kind, "opens_year": None, "opens_month": None, "opens_day": None,
            "closes_year": None, "closes_month": None, "closes_day": None}
    return {**base, **dates}


@pytest.mark.parametrize(
    ("extracted", "reachable", "expected"),
    [
        # 原文寫明這一屆不提供（段 3 會封存）
        ({"offered": "no", "windows": [window()]}, True, "not_offered"),
        # 網站最近抓不到：資料停在以前
        ({"windows": []}, False, "unreachable"),
        # Coventry：「There is no application required ... automatically credited」
        ({"how_to_apply": "automatic", "windows": []}, True, "no_application"),
        ({"how_to_apply": "after_enrolment", "windows": []}, True, "no_application"),
        # 隨入學一起審，但這幾頁沒寫入學截止日
        ({"how_to_apply": "with_admission", "windows": []}, True, "admission_date_elsewhere"),
        # 11-21 重新檢查：隨入學一起審，但原文說日期還沒公布（「applications open late November 2026」），
        # 原因是「還沒公布」，不是「入學日期在別頁」
        ({"how_to_apply": "with_admission", "missing_date": "not_announced", "windows": []}, True, "not_announced"),
        # BIOPHAM：「NEXT CALL FOR APPLICATIONS Opening: 1 November 2026」，只有開放日
        ({"windows": [window(opens_year=2026, opens_month=11, opens_day=1)]}, True, "not_announced"),
        ({"missing_date": "not_announced", "windows": []}, True, "not_announced"),
        # Chevening：「October 2026 Applications close」，沒寫哪一天
        ({"windows": [window(closes_year=2026, closes_month=10)]}, True, "month_only"),
        ({"missing_date": "rolling", "windows": []}, True, "rolling"),
        ({"missing_date": "elsewhere", "windows": []}, True, "elsewhere"),
        # 只有付款期限（早鳥折扣）也不是獎學金的截止日；什麼都沒提
        ({"windows": [window("payment", closes_year=2027, closes_month=8, closes_day=1)]}, True, "not_found"),
        ({}, True, "not_found"),
    ],
)
def test_the_first_matching_reason_explains_a_missing_application_period(
    extracted: dict[str, Any], reachable: bool, expected: str
) -> None:
    assert cycles.no_date_reason(extracted, has_cycles=False, reachable=reachable) == expected


def test_a_scholarship_with_an_application_period_needs_no_reason() -> None:
    assert cycles.no_date_reason({"how_to_apply": "automatic"}, has_cycles=True, reachable=True) is None
