"""國家群組展開成國碼（D1 C，ADR-109）。"""

from app.features.scholarships import groups


def test_groups_expand_to_country_codes_together_with_listed_countries() -> None:
    # 「歐盟國家與瑞士」：群組展開，另外寫的國家照留
    scope, codes = groups.expand("listed", ["CH"], ["EU"])
    assert scope == "listed" and len(codes) == 28 and {"FR", "GR", "CH"} <= set(codes) and "NO" not in codes
    # 「非歐盟／EEA 學生」：排除兩個群組，重複的國家只留一次
    scope, codes = groups.expand("excluded", [], ["EU", "eea"])
    assert scope == "excluded" and len(codes) == 30 and {"IS", "LI", "NO"} <= set(codes)
    # 非洲聯盟 55 個會員
    scope, codes = groups.expand("listed", [], ["AU"])
    assert scope == "listed" and len(codes) == 55 and "NG" in codes and "TW" not in codes


def test_erasmus_partner_countries_are_everyone_except_programme_countries() -> None:
    assert groups.expand("listed", [], ["ERASMUS_PARTNER"]) == ("excluded", list(groups.GROUPS["ERASMUS_PROGRAMME"]))


def test_an_unknown_group_leaves_the_nationality_unclear() -> None:
    # 學校自訂的 Tier 1：不知道有哪些國家，國籍標待確認（unclear），另外寫的國家照留
    assert groups.expand("listed", ["FR"], ["Tier 1 countries"]) == ("unclear", ["FR"])
    # 沒有群組：原樣
    assert groups.expand("excluded", ["CN"], []) == ("excluded", ["CN"])
