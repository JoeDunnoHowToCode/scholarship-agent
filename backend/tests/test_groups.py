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


def test_erasmus_world_regions_expand_to_their_countries() -> None:
    # 總檢查 A1／C2（ADR-112）：MULTICOM 的地區名額寫「Sub-Saharan Africa」「Latin America」「Asia」，
    # 程式不認得就改成待確認。清單照 Erasmus+ Programme Guide 的 eligible countries（2026-11-20 查證）
    scope, africa = groups.expand("listed", [], ["SUB_SAHARAN_AFRICA"])
    assert scope == "listed" and len(africa) == 49 and {"NG", "ZA", "CD", "SS"} <= set(africa)
    _, asia = groups.expand("listed", [], ["ASIA"])
    assert len(asia) == 25 and {"IN", "VN", "TW", "JP", "KR", "HK"} <= set(asia)  # 含高所得國家與地區
    _, south = groups.expand("listed", [], ["NEIGHBOURHOOD_SOUTH"])
    assert set(south) == {"DZ", "EG", "IL", "JO", "LB", "LY", "MA", "PS", "SY", "TN"}
    _, latin = groups.expand("listed", [], ["LATIN_AMERICA"])
    assert len(latin) == 17 and "TW" not in latin


def test_a_category_that_repeats_the_scholarships_exclusion_is_not_limited_to_those_groups() -> None:
    # 11-21 重新檢查（ADR-120）：ITU 整筆「排除歐盟、歐洲經濟區」，AI 把 EU、EEA 也抄進唯一的類別；
    # 類別的代號代表「只給這些地區」，評分因此把非歐盟的人判成不符合。抄來的代號不算類別的地區
    assert groups.category_regions("excluded", ["EU", "EEA"], ["EU", "EEA"]) == []
    assert groups.category_regions("excluded", ["EU", "EEA"], ["eea"]) == []
    # 真的地區名額照留：整筆不限國籍，類別只給亞洲；整筆排除歐盟，類別只給非洲
    assert groups.category_regions("all", [], ["ASIA"]) == ["ASIA"]
    assert groups.category_regions("excluded", ["EU"], ["SUB_SAHARAN_AFRICA"]) == ["SUB_SAHARAN_AFRICA"]
    # 整筆不是排除時，類別寫 Programme countries 是真的「只給」（Erasmus Mundus 的計畫國名額）
    assert groups.category_regions("all", [], ["ERASMUS_PROGRAMME"]) == ["ERASMUS_PROGRAMME"]
