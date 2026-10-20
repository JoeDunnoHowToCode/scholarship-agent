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
