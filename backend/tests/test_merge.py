"""長文件合併規則的單元測試（ADR-034、docs/day-03.md「Claude 自行決定」第 9 點）。"""

from typing import Any

from app.features.scholarships import merge
from app.features.scholarships.schemas import (
    AmountDraft,
    CategoryFact,
    Outline,
    OutlineCategory,
    RequirementDraft,
    SectionFacts,
    WindowDraft,
)

EMPTY: dict[str, Any] = {
    "provider": None,
    "countries": [],
    "degrees": [],
    "degrees_evidence": None,
    "fields": [],
    "coverage": None,
    "amount": None,
    "amounts": [],
    "nationality_scope": "unclear",
    "nationalities": [],
    "nationality_evidence": None,
    "nationality_conditions": None,
    "language_requirements": None,
    "other_eligibility": None,
    "requires_admission": None,
    "total_quota": None,
    "windows": [],
    "category_facts": [],
    "requirements": [],
}


def section(**fields: Any) -> SectionFacts:
    # 一節裡沒提到的欄位都是空的，測試只寫出這一節有提到的
    return SectionFacts(**{**EMPTY, **fields})


OUTLINE = Outline(name="GSSA", name_zh="留學獎學金", provider="教育部", category_names=[])


def test_first_value_wins_and_a_different_value_is_a_conflict() -> None:
    # 總名額取第一個有值的；後面出現不同的值，記成衝突，交給驗證者標待確認
    # （ADR-047 之後截止日可以有很多個，不再是「只該有一個值」的欄位，改用總名額當例子）
    result = merge.merge_sections(
        OUTLINE,
        [section(), section(total_quota=225), section(total_quota=190)],
    )
    assert result.draft.total_quota == 225
    assert result.conflicts == ["total_quota"]


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


def test_nationality_scope_prefers_listed_then_excluded_then_all() -> None:
    # ADR-043：只要有一節列出限定的國家，就以列出的為準；國家清單取這一類各節的聯集
    result = merge.merge_sections(
        OUTLINE,
        [
            section(nationality_scope="all", nationality_evidence="all nationalities"),
            section(nationality_scope="listed", nationalities=["Taiwan", "Japan"],
                    nationality_evidence="citizens of Taiwan or Japan"),
            section(nationality_scope="listed", nationalities=["Japan", "South Korea"],
                    nationality_evidence="and South Korea"),
            section(),
        ],
    )
    assert result.draft.nationality_scope == "listed"
    assert result.draft.nationalities == ["Taiwan", "Japan", "South Korea"]
    assert result.draft.nationality_evidence == "citizens of Taiwan or Japan"


def test_degrees_evidence_comes_from_the_first_section_with_degrees() -> None:
    result = merge.merge_sections(
        OUTLINE,
        [
            section(degrees_evidence="與學位無關的句子"),
            section(degrees=["phd"], degrees_evidence="一律以攻讀博士學位為限"),
        ],
    )
    assert result.draft.degrees_evidence == "一律以攻讀博士學位為限"


def fact(applies_to: list[str], **fields: Any) -> CategoryFact:
    empty: dict[str, Any] = {
        "quota": None, "degrees": [], "countries": [], "amount": None,
        "eligibility": None, "evidence": None,
    }
    return CategoryFact(applies_to=applies_to, **{**empty, **fields})


def test_category_rules_use_explicit_facts_before_all() -> None:
    # 教育部的例子：第 3 章寫學位規則，第 4 章寫名額，另有一條適用所有類別的規則
    # 類別先用明確點名它的規則；沒有才用「全部」的規則
    outline = Outline(
        name="GSSA", name_zh=None, provider=None,
        category_names=["一般學群", "北歐國家", "特殊生"],
    )
    result = merge.merge_sections(
        outline,
        [
            section(category_facts=[
                fact(["一般學群", "北歐國家"], degrees=["phd"], evidence="一律以攻讀博士學位為限"),
            ]),
            section(category_facts=[
                fact(["一般學群"], quota=155),
                fact(["北歐國家"], quota=10, countries=["Denmark", "Sweden"]),
            ]),
            section(category_facts=[
                fact(["all"], degrees=["master", "phd"], amount="每年 1 萬 6 千美元",
                     eligibility="需有入學許可"),
            ]),
        ],
    )
    general, nordic, special = result.draft.categories
    assert (general.name, general.quota, general.degrees) == ("一般學群", 155, ["phd"])
    assert general.degrees_evidence == "一律以攻讀博士學位為限"  # ADR-046：學位有自己的引用
    assert general.amount == "每年 1 萬 6 千美元"
    assert general.eligibility == "需有入學許可"
    assert (nordic.quota, nordic.countries) == (10, ["Denmark", "Sweden"])
    assert (special.quota, special.degrees) == (None, ["master", "phd"])


def test_without_category_names_one_category_is_named_after_the_scholarship() -> None:
    # 只有一種名額的獎學金也要有一筆類別（ADR-040）；學位與國家沒有規則時用整個獎學金的
    result = merge.merge_sections(
        OUTLINE,
        [section(degrees=["master"], countries=["Sweden"],
                 category_facts=[fact(["all"], quota=20)])],
    )
    (only,) = result.draft.categories
    assert (only.name, only.quota, only.degrees, only.countries) == (
        "GSSA", 20, ["master"], ["Sweden"],
    )


def test_unknown_category_name_is_dropped_with_a_warning() -> None:
    # 第二輪的 AI 寫了大綱沒有的類別名稱：不能猜它指哪個類別，丟掉並記警告
    outline = Outline(name="GSSA", name_zh=None, provider=None, category_names=["北歐國家"])
    result = merge.merge_sections(
        outline,
        [section(category_facts=[fact(["北歐國家"], quota=10), fact(["北歐"], quota=99)])],
    )
    assert [c.quota for c in result.draft.categories] == [10]
    assert result.warnings == ["未知類別：北歐"]


def requirement(doc_type: str, **fields: Any) -> RequirementDraft:
    empty: dict[str, Any] = {
        "details": None, "required": None, "count": None, "category": None, "evidence": None,
    }
    return RequirementDraft(doc_type=doc_type, **{**empty, **fields})  # type: ignore[arg-type]


def test_requirements_are_unioned_without_duplicates() -> None:
    # 同一份文件在兩節都出現（類型、類別、要求都一樣，只差空白）只留一筆
    # 寫了大綱沒有的類別：不能猜，改成所有類別都要交，並記警告
    outline = Outline(name="GSSA", name_zh=None, provider=None, category_names=["北歐國家"])
    result = merge.merge_sections(
        outline,
        [
            section(requirements=[requirement("cv", details="英文履歷"),
                                  requirement("portfolio", category="北歐國家")]),
            section(requirements=[requirement("cv", details="英文 履歷"),
                                  requirement("transcript", category="藝術")]),
        ],
    )
    assert [(r.doc_type, r.category) for r in result.draft.requirements] == [
        ("cv", None), ("portfolio", "北歐國家"), ("transcript", None),
    ]
    assert result.warnings == ["未知類別：藝術"]


def test_same_document_type_keeps_one_row_with_the_longest_details() -> None:
    # 簡章常在好幾節重複列同一份文件（正文、檢核表、報名流程），寫法不同
    # 同一類型、同一類別只留一筆：保留寫得最詳細的；份數取有寫的；任一處說必要就是必要
    # other 是好幾種不同文件的統稱，只有要求文字一樣才算重複
    result = merge.merge_sections(
        OUTLINE,
        [
            section(requirements=[requirement("cv", details="履歷表", required=True),
                                  requirement("other", details="排名資料")]),
            section(requirements=[requirement("cv", details="包括自我介紹、學經歷", count=1),
                                  requirement("other", details="指導教授簡介")]),
        ],
    )
    assert [(r.doc_type, r.details, r.count, r.required) for r in result.draft.requirements] == [
        ("cv", "包括自我介紹、學經歷", 1, True),
        ("other", "排名資料", None, None),
        ("other", "指導教授簡介", None, None),
    ]


def test_outline_details_fill_categories_without_explicit_facts() -> None:
    # 第一輪讀過全文，知道「北歐國家」只能讀博士（規則寫在別章、用「一般生」統稱）
    # 優先順序：明確點名的規則 > 第一輪的類別資料 > 「全部」的規則 > 整個獎學金的值
    outline = Outline(
        name="GSSA", name_zh=None, provider=None,
        category_names=["一般學群", "北歐國家"],
        category_details=[
            OutlineCategory(name="一般學群", quota=150, degrees=["phd"], countries=[]),
            OutlineCategory(name="北歐國家", quota=10, degrees=["phd"], countries=["Sweden"]),
        ],
    )
    result = merge.merge_sections(
        outline,
        [section(degrees=["bachelor", "master", "phd"], category_facts=[
            fact(["一般學群"], quota=155, degrees=["phd", "master"]),
            fact(["all"], degrees=["master", "phd"]),
        ])],
    )
    general, nordic = result.draft.categories
    assert (general.quota, general.degrees) == (155, ["phd", "master"])
    assert (nordic.quota, nordic.degrees, nordic.countries) == (10, ["phd"], ["Sweden"])


def test_group_quota_is_not_copied_to_each_category() -> None:
    # 教育部的真實情況：第二輪把「選送赴特定國家名額計 35 名」寫成一條規則，
    # applies_to 同時列了北歐、新南向甲、新南向乙。35 是三類加起來的總數，不是每一類的名額
    # 名額只能來自只點名一個類別的規則；多個類別的規則只提供學位、國家等其他資料
    outline = Outline(
        name="GSSA", name_zh=None, provider=None,
        category_names=["北歐國家", "新南向國家甲", "新南向國家乙"],
        category_details=[
            OutlineCategory(name="北歐國家", quota=10, degrees=["phd"], countries=[]),
            OutlineCategory(name="新南向國家甲", quota=15, degrees=["phd"], countries=[]),
            OutlineCategory(name="新南向國家乙", quota=10, degrees=["phd"], countries=[]),
        ],
    )
    result = merge.merge_sections(
        outline,
        [section(category_facts=[
            fact(["北歐國家", "新南向國家甲", "新南向國家乙"], quota=35),
            fact(["新南向國家甲"], quota=15),
        ])],
    )
    assert [c.quota for c in result.draft.categories] == [10, 15, 10]


def test_evidence_follows_where_quota_and_degrees_come_from() -> None:
    # ADR-046：名額的引用跟著名額的來源，學位的引用與條件跟著學位的來源
    # 教育部北歐：名額來自第二輪只點名北歐的規則；學位與條件來自第一輪讀全文
    outline = Outline(
        name="GSSA", name_zh=None, provider=None,
        category_names=["北歐國家", "新南向國家甲"],
        category_details=[
            OutlineCategory(
                name="北歐國家", quota=None, degrees=["phd", "master"], countries=[],
                degrees_evidence="一般生一律以攻讀博士學位為限",
                degree_conditions="碩士限藝術學群、建築規劃與設計學群",
            ),
            OutlineCategory(name="新南向國家甲", quota=15, degrees=[], countries=[],
                            quota_evidence="甲、印尼……不丹：15 名"),
        ],
    )
    result = merge.merge_sections(
        outline,
        [section(category_facts=[
            fact(["北歐國家"], quota=10, evidence="(1)北歐國家(丹麥、瑞典、挪威、芬蘭、冰島)：10 名"),
            fact(["新南向國家甲"], degrees=["master", "phd"], evidence="選送赴特定國家「新南向國家」者，得攻讀碩士或博士學位"),
        ])],
    )
    nordic, south = result.draft.categories
    assert nordic.quota_evidence == "(1)北歐國家(丹麥、瑞典、挪威、芬蘭、冰島)：10 名"
    assert nordic.degrees_evidence == "一般生一律以攻讀博士學位為限"
    assert nordic.degree_conditions == "碩士限藝術學群、建築規劃與設計學群"
    assert south.quota_evidence == "甲、印尼……不丹：15 名"
    assert south.degrees_evidence == "選送赴特定國家「新南向國家」者，得攻讀碩士或博士學位"
    assert south.degree_conditions is None


def test_category_inheriting_program_degrees_also_inherits_the_quote() -> None:
    # 類別沒有自己的學位規則，學位用整個獎學金的；學位的引用也要一起帶過來，不然學位檢查找不到依據
    result = merge.merge_sections(
        OUTLINE,
        [section(degrees=["master"], degrees_evidence="a two-year Master's programme")],
    )
    (only,) = result.draft.categories
    assert (only.degrees, only.degrees_evidence) == (["master"], "a two-year Master's programme")


def test_card_whose_quote_never_mentions_degrees_does_not_set_degrees() -> None:
    # 教育部北歐的真實情況：第二輪把學位寫在名額那張卡上，但那張卡的引用只講名額；
    # 這種卡的學位不能蓋掉第一輪有依據的學位、引用與條件（ADR-046）
    outline = Outline(
        name="GSSA", name_zh=None, provider=None, category_names=["北歐國家"],
        category_details=[OutlineCategory(
            name="北歐國家", quota=10, degrees=["master", "phd"], countries=[],
            degrees_evidence="一般生一律以攻讀博士學位為限，惟「藝術學群」……得攻讀碩士或博士學位",
            degree_conditions="碩士限藝術學群、建築規劃與設計學群",
        )],
    )
    result = merge.merge_sections(
        outline,
        [section(category_facts=[
            fact(["北歐國家"], quota=10, degrees=["phd"], evidence="(1)北歐國家(丹麥、瑞典、挪威、芬蘭、冰島)：10 名。"),
        ])],
    )
    (nordic,) = result.draft.categories
    assert nordic.degrees == ["master", "phd"]
    assert nordic.degree_conditions == "碩士限藝術學群、建築規劃與設計學群"
    assert nordic.quota == 10


def window(**fields: Any) -> WindowDraft:
    empty: dict[str, Any] = {
        "label": None, "intake": None, "opens_year": None, "opens_month": None, "opens_day": None,
        "closes_year": None, "closes_month": None, "closes_day": None, "closes_time": None,
        "timezone": None, "nationality_scope": "all", "nationalities": [], "funding": "any",
        "evidence": None,
    }
    return WindowDraft(**{**empty, **fields})


def test_windows_from_all_sections_are_kept_once_each() -> None:
    # 學程 20 的例子：夥伴國 2/28、歐盟國 3/31 兩個截止日都要留下；
    # 另一節又寫了一次夥伴國 2/28（只是引用的句子不同），只留一筆
    partner: dict[str, Any] = {
        "closes_year": 2027, "closes_month": 2, "closes_day": 28,
        "nationality_scope": "excluded", "nationalities": ["France"], "funding": "scholarship",
    }
    result = merge.merge_sections(
        OUTLINE,
        [
            section(windows=[window(**partner, evidence="Feb 28th 2027"),
                             window(closes_year=2027, closes_month=3, closes_day=31,
                                    nationality_scope="listed", nationalities=["France"])]),
            section(windows=[window(**partner, evidence="Application deadline for Partners Countries")]),
        ],
    )
    assert [(w.closes_month, w.closes_day, w.nationality_scope) for w in result.draft.windows] == [
        (2, 28, "excluded"), (3, 31, "listed"),
    ]
    assert result.draft.windows[0].evidence == "Feb 28th 2027"


def test_same_closing_day_for_the_same_nationalities_is_one_window() -> None:
    # 教育部的真實情況：2/13 的截止日在三個章節各抽到一次，寫法不同
    # （一筆寫了「申請獎學金」和時區、一筆沒寫申請類型、一筆連時區都沒寫）
    # 截止日同一天、適用國籍一樣，就是同一個窗口：留下資訊最完整的那筆
    complete = window(closes_year=2026, closes_month=2, closes_day=13, closes_time="12:00",
                      timezone="Asia/Taipei", funding="scholarship", label="開放網路報名起訖時間")
    result = merge.merge_sections(
        OUTLINE,
        [
            section(windows=[window(closes_year=2026, closes_month=2, closes_day=13,
                                    closes_time="12:00")]),
            section(windows=[complete]),
            section(windows=[window(closes_year=2026, closes_month=2, closes_day=13,
                                    timezone="Asia/Taipei")]),
        ],
    )
    assert result.draft.windows == [complete]


def test_amounts_from_all_sections_are_kept_once_each() -> None:
    # 教育部簡章：一般生的金額在兩節各抽到一次（寫法、引用不同），勵學優秀生只在第二節
    general = AmountDraft(
        value=16000, currency="USD", period="year", kind="living_allowance",
        applies_to="一般生", evidence="一般生每人每年核發 1 萬 6 千美元",
    )
    general_again = AmountDraft(
        value=16000, currency="usd", period="year", kind="living_allowance",
        applies_to=" 一般生", evidence="一般生：每年 16,000 美元",
    )
    excellent = AmountDraft(
        value=30000, currency="USD", period="year", kind="living_allowance",
        applies_to="勵學優秀生", evidence="勵學優秀生每人每年核發 3 萬美元",
    )
    # 數字、幣別、期間、用途、適用對象都一樣的，只留第一次出現的那筆與它的引用（幣別不分大小寫、適用對象不管空白）
    assert merge.merge_amounts([[general], [general_again, excellent]]) == [general, excellent]
