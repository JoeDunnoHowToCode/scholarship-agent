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
