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


def test_category_name_must_be_short_and_in_the_source() -> None:
    source = "(1)北歐國家(丹麥、瑞典、挪威、芬蘭、冰島)：10 名。\n甲、 印尼、菲律賓、泰國、馬來西亞、汶萊、越南、緬甸、柬埔寨、寮國：15 名。"
    assert rules.category_name_issue("北歐國家", source) is None
    # 把整串國名當成類別名稱：雖然在原文裡，但太長
    assert rules.category_name_issue("印尼、菲律賓、泰國、馬來西亞、汶萊、越南、緬甸、柬埔寨、寮國", source) == "name_too_long"
    assert rules.category_name_issue("新南向國家甲", source) == "name_not_in_source"
