"""國家群組（D1 C，ADR-109）：原文用群組寫國籍時，AI 填群組代號，程式在這裡展開成 ISO 3166-1 國碼。

清單放在程式裡（像 ADR-054 的 Erasmus+ 清單），每份附官方出處與查證日期；群組成員改變時要更新。
"""

# 歐盟 27 國；希臘用 ISO 的 GR（歐盟自己的代碼是 EL）
# 出處：https://european-union.europa.eu/principles-countries-history/eu-countries_en（2026-11-16 查證）
EU = (
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
)
# 歐洲經濟區＝歐盟＋冰島、列支敦斯登、挪威（瑞士不在內）
# 出處：https://www.efta.int/eea（2026-11-16 查證）
EEA = (*EU, "IS", "LI", "NO")
# Erasmus+ Programme countries＝歐盟＋6 個參與國（2026 Programme Guide；瑞士、英國預計 2027 加入，出新版時再查）
# 出處：https://erasmus-plus.ec.europa.eu/programme-guide/part-a/eligible-countries（2026-11-16 查證）
ERASMUS_PROGRAMME = (*EU, "IS", "LI", "NO", "MK", "RS", "TR")
# 非洲聯盟 55 個會員（含暫停會籍的）；撒拉威（SADR）沒有自己的 ISO 國碼，用西撒哈拉的 EH
# 出處：https://au.int/en/member_states/countryprofiles2（2026-11-16 查證）
AU = (
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM", "CG", "CD", "CI", "DJ", "EG", "GQ", "ER",
    "SZ", "ET", "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW", "ML", "MR", "MU", "MA", "MZ",
    "NA", "NE", "NG", "RW", "EH", "ST", "SN", "SC", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG", "ZM", "ZW",
)
# 西巴爾幹（Erasmus+ 第 1 區，不是參與國）；科索沃沒有正式的 ISO 國碼，用歐盟實際使用的 XK
# 出處：同上 Erasmus+ eligible countries（2026-11-16 查證）
WESTERN_BALKANS = ("AL", "BA", "XK", "ME")

# Erasmus+ 的世界地區（不屬於計畫的第三國，Region 2–12）：Erasmus Mundus 的地區名額照這些地區分（ADR-112）
# 出處：https://erasmus-plus.ec.europa.eu/programme-guide/part-a/eligible-countries（2026-11-20 查證）
NEIGHBOURHOOD_EAST = ("AM", "AZ", "BY", "GE", "MD", "UA")  # Region 2
# Region 3「South-Mediterranean countries」，Erasmus Mundus 學程常寫成 Neighbourhood South
NEIGHBOURHOOD_SOUTH = ("DZ", "EG", "IL", "JO", "LB", "LY", "MA", "PS", "SY", "TN")
# Region 5：官方把高所得國家與地區也列在 Asia 底下（台灣在這裡）；地區名額常只給前一群，所以分開記
ASIA_HIGH_INCOME = ("BN", "HK", "JP", "KR", "MO", "SG", "TW")
ASIA = (
    "BD", "BT", "KH", "CN", "KP", "IN", "ID", "LA", "MY", "MV", "MN", "MM", "NP", "PK", "PH", "LK", "TH", "VN",
    *ASIA_HIGH_INCOME,
)
CENTRAL_ASIA = ("AF", "KZ", "KG", "TJ", "TM", "UZ")  # Region 6
MIDDLE_EAST_HIGH_INCOME = ("BH", "KW", "OM", "QA", "SA", "AE")
MIDDLE_EAST = ("IR", "IQ", "YE", *MIDDLE_EAST_HIGH_INCOME)  # Region 7
PACIFIC_HIGH_INCOME = ("AU", "CK", "NZ")
PACIFIC = (  # Region 8
    "FJ", "KI", "MH", "FM", "NR", "NU", "PW", "PG", "WS", "SB", "TL", "TO", "TV", "VU", *PACIFIC_HIGH_INCOME,
)
SUB_SAHARAN_AFRICA = (  # Region 9
    "AO", "BJ", "BW", "BF", "BI", "CM", "CV", "CF", "TD", "KM", "CG", "CD", "CI", "DJ", "GQ", "ER", "ET", "SZ",
    "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "MG", "MW", "ML", "MR", "MU", "MZ", "NA", "NE", "NG", "RW",
    "ST", "SN", "SC", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG", "UG", "ZM", "ZW",
)
LATIN_AMERICA = (  # Region 10
    "AR", "BO", "BR", "CL", "CO", "CR", "EC", "SV", "GT", "HN", "MX", "NI", "PA", "PY", "PE", "UY", "VE",
)
CARIBBEAN = (  # Region 11
    "AG", "BS", "BB", "BZ", "CU", "DM", "DO", "GD", "GY", "HT", "JM", "KN", "LC", "VC", "SR", "TT",
)
# 高所得的部分：地區名額不一定給它們，評分時算待確認（ADR-112）
HIGH_INCOME = frozenset((*ASIA_HIGH_INCOME, *MIDDLE_EAST_HIGH_INCOME, *PACIFIC_HIGH_INCOME))

GROUPS: dict[str, tuple[str, ...]] = {
    "EU": EU,
    "EEA": EEA,
    "ERASMUS_PROGRAMME": ERASMUS_PROGRAMME,
    "AU": AU,
    "WESTERN_BALKANS": WESTERN_BALKANS,
    "NEIGHBOURHOOD_EAST": NEIGHBOURHOOD_EAST,
    "NEIGHBOURHOOD_SOUTH": NEIGHBOURHOOD_SOUTH,
    "ASIA": ASIA,
    "CENTRAL_ASIA": CENTRAL_ASIA,
    "MIDDLE_EAST": MIDDLE_EAST,
    "PACIFIC": PACIFIC,
    "SUB_SAHARAN_AFRICA": SUB_SAHARAN_AFRICA,
    "LATIN_AMERICA": LATIN_AMERICA,
    "CARIBBEAN": CARIBBEAN,
}


def expand(scope: str, nationalities: list[str], groups: list[str]) -> tuple[str, list[str]]:
    """把群組展開成國碼，和另外寫的國家合在一起；回傳（國籍範圍, 國碼清單）。

    - Erasmus+ Partner countries 是「Programme countries 以外的所有國家」：只有這個群組時，換成排除 Programme countries
    - 不認識的群組（例如學校自訂的 Tier 1）不知道有哪些國家，國籍範圍改成 unclear（待確認），另外寫的國家照留
    """
    codes = [group.strip().upper() for group in groups]
    if not codes:
        return scope, nationalities
    if codes == ["ERASMUS_PARTNER"] and scope == "listed" and not nationalities:
        return "excluded", list(ERASMUS_PROGRAMME)
    if any(code not in GROUPS for code in codes):
        return "unclear", nationalities
    expanded = [country for code in codes for country in GROUPS[code]]
    return scope, list(dict.fromkeys([*nationalities, *expanded]))  # 去掉重複、保持順序
