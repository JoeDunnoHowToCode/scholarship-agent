"""抽取結果程式檢查的單元測試（ADR-045）。"""

from app.features.scholarships import rules


def test_deadline_year_must_be_in_the_quote() -> None:
    # 原文只寫「1st of March」，模型自己補的年份不算（學程 82 的真實例子）
    assert rules.deadline_year_in_quote(2027, "Deadline: 15 January 2027 (CET)")
    assert not rules.deadline_year_in_quote(2025, "1st of March: All nationals applying")
    assert not rules.deadline_year_in_quote(2027, None)
    # 民國年：2026 年是民國 115 年
    assert rules.deadline_year_in_quote(2026, "115 年 2 月 13 日(五)中午 12:00 截止")
