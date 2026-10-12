"""抽取結果程式檢查的單元測試（ADR-045）。"""

from app.features.scholarships import rules


def test_deadline_year_must_be_in_the_quote() -> None:
    # 原文只寫「1st of March」，模型自己補的年份不算（學程 82 的真實例子）
    assert rules.deadline_year_in_quote(2027, "Deadline: 15 January 2027 (CET)")
    assert not rules.deadline_year_in_quote(2025, "1st of March: All nationals applying")
    assert not rules.deadline_year_in_quote(2027, None)
    # 民國年：2026 年是民國 115 年
    assert rules.deadline_year_in_quote(2026, "115 年 2 月 13 日(五)中午 12:00 截止")


def test_degree_keywords_must_appear_in_the_quotes() -> None:
    # 教育部的例子：原文是「得攻讀碩士或博士學位」，模型卻每次都加上 bachelor
    quotes = ["一般生一律以攻讀博士學位為限", "得攻讀碩士或博士學位"]
    assert rules.degree_supported("master", quotes)
    assert rules.degree_supported("phd", quotes)
    assert not rules.degree_supported("bachelor", quotes)
    assert rules.degree_supported("master", [None, "study for a one-year Master's degree"])
    assert rules.degree_supported("phd", ["PhD positions"])
    assert not rules.degree_supported("master", [None])
