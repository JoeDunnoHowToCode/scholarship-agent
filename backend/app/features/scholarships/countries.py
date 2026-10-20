"""國家代碼（ADR-054）：國家一律存 ISO 3166-1 兩碼國碼（TW、KR、CZ…）；這裡檢查代碼、給顯示名稱、列出原文可能出現的國名。"""

import pycountry  # ISO 3166 的國家資料（國碼、正式名稱、常用名稱）

EXTRA_CODES = {"XK": "Kosovo"}  # ISO 沒有列、但我們接受的代碼（Kosovo 沒有正式國碼，慣例用 XK）


def valid_code(code: str) -> str | None:
    """把 AI 填的國碼整理成大寫（" tw " → "TW"）；不存在的代碼回傳 None。"""
    cleaned = code.strip().upper()
    # pycountry 和 EXTRA_CODES 裡都只有兩個字母的代碼，所以國名（例如 Taiwan）一定查不到
    if pycountry.countries.get(alpha_2=cleaned) is not None or cleaned in EXTRA_CODES:
        return cleaned
    return None


def clean_codes(codes: list[str]) -> tuple[list[str], list[str]]:
    """把 AI 填的國碼分成（有效, 無效）兩組：有效的轉大寫，無效的保留原本寫法；重複的只留第一次出現的。"""
    valid: list[str] = []
    invalid: list[str] = []
    for code in codes:
        cleaned = valid_code(code)
        if cleaned is None:
            invalid.append(code.strip())
        else:
            valid.append(cleaned)
    # dict 會記住放入順序，用來去重又保留順序
    return list(dict.fromkeys(valid)), list(dict.fromkeys(invalid))


# 我們自己決定的顯示名稱，優先於 pycountry（ADR-054）；例如台灣不用 ISO 的「Taiwan, Province of China」
DISPLAY_NAMES = {"TW": "Taiwan", "KR": "South Korea", "KP": "North Korea", **EXTRA_CODES}

# 原文常見、但 pycountry 不一定有的寫法：舊名、簡稱、中文名
ALIASES = {
    "TW": ["Republic of China", "Chinese Taipei", "台灣", "臺灣", "中華民國"],
    "KR": ["Korea", "Republic of Korea"],
    "KP": ["DPRK"],
    "CZ": ["Czech Republic"],
    "TR": ["Turkey"],
    "MK": ["Macedonia"],
    "GB": ["United Kingdom", "UK", "Great Britain"],
    "US": ["United States", "USA"],
    "NL": ["Holland"],
    "VN": ["Vietnam"],
    "RU": ["Russia"],
    "LA": ["Laos"],
}


def display_name(code: str) -> str:
    """畫面上顯示的國名：先用我們自己的名稱，再用 pycountry 的常用名稱，最後用 pycountry 的名稱。"""
    if code in DISPLAY_NAMES:
        return DISPLAY_NAMES[code]
    country = pycountry.countries.get(alpha_2=code)
    if country is None:
        return code  # 不認得的代碼直接顯示代碼
    # 只有部分國家有常用名稱（例如 Viet Nam 的 Vietnam）；沒有就用名稱
    return getattr(country, "common_name", country.name)


def names_for(code: str) -> list[str]:
    """原文裡可能用來指這個國家的寫法，用來檢查原文真的有提到這個國家。"""
    names = [display_name(code)]
    country = pycountry.countries.get(alpha_2=code)
    if country is not None:
        # pycountry 的三種寫法：名稱、正式全名、常用名稱；有些國家沒有後兩種
        for field in ("name", "official_name", "common_name"):
            if hasattr(country, field):
                names.append(getattr(country, field))
    names += ALIASES.get(code, [])
    return list(dict.fromkeys(names))  # 去掉重複，保留第一次出現的順序
