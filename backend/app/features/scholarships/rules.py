"""抽取結果的程式檢查（ADR-045）：不花 AI 費用，擋下模型每次都會犯的錯。"""

import re
import unicodedata
from typing import Literal

from app.features.documents.checks import quote_in_source

ROC_OFFSET = 1911  # 民國年 + 1911 = 西元年


def _normalize(text: str) -> str:
    """全形轉半形（NFKC），去掉千分位逗號。"""
    return unicodedata.normalize("NFKC", text).replace(",", "")


def _has_number(number: int, text: str) -> bool:
    # 前後不能緊接著其他數字：找 2027 時，20270 不算
    return re.search(rf"(?<!\d){number}(?!\d)", _normalize(text)) is not None


def deadline_year_in_quote(year: int, quote: str | None) -> bool:
    """截止日的年份要寫在引用裡，不能是模型自己補的；民國年（例如 115 年）也算。"""
    if not quote:
        return False
    roc = re.search(rf"(?<!\d){year - ROC_OFFSET}\s*年", _normalize(quote))
    return _has_number(year, quote) or roc is not None


# 每種學位在原文裡常見的寫法（不分大小寫）
DEGREE_KEYWORDS = {
    "bachelor": re.compile(r"bachelor|undergraduate|\bB\.?Sc\b|\bBA\b|學士|大學部", re.IGNORECASE),
    "master": re.compile(r"master|\bM\.?Sc\b|\bMA\b|\bMBA\b|\bLLM\b|碩士", re.IGNORECASE),
    "phd": re.compile(r"ph\.?\s?d|doctor|doctoral|博士", re.IGNORECASE),
}


def degree_supported(degree: str, quotes: list[str | None]) -> bool:
    """這個學位的關鍵字要出現在任一句引用裡（例如原文沒寫「學士」就不能填 bachelor）。"""
    return any(quote and DEGREE_KEYWORDS[degree].search(quote) for quote in quotes)


MAX_CATEGORY_NAME = 20  # 中文類別名稱最多幾個字；更長的通常是把國家清單當成名稱
MAX_CATEGORY_WORDS = 8  # 英文類別名稱最多幾個字（以空白分開的字）
CJK = re.compile(r"[\u4e00-\u9fff]")


def category_name_issue(name: str, source: str) -> str | None:
    """類別名稱的問題：太長、或原文裡找不到；沒問題回傳 None。"""
    too_long = (
        len(name) > MAX_CATEGORY_NAME if CJK.search(name) else len(name.split()) > MAX_CATEGORY_WORDS
    )
    if too_long:
        return "name_too_long"
    if not quote_in_source(name, source):
        return "name_not_in_source"
    return None


def number_in_source(number: int, source: str) -> bool:
    """名額這類數字要在原文找得到（1,400 和 1400 視為相同）。"""
    return _has_number(number, source)


def name_in_source(name: str, source: str) -> bool:
    """國名要在原文找得到（不分大小寫，整個字比對：Niger 不會因為 Nigeria 而通過）。"""
    pattern = rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])"
    return re.search(pattern, _normalize(source), re.IGNORECASE) is not None


def quota_sum_mismatch(total: int | None, quotas: list[int | None]) -> bool:
    """原文寫了總名額、每個類別也都有名額時，加總要相等；資料不齊就不比。"""
    if total is None or not quotas or any(quota is None for quota in quotas):
        return False
    return sum(quota for quota in quotas if quota is not None) != total


# Erasmus+ 的「Programme countries」（現在也寫成「歐盟成員國與關聯第三國」）：歐盟 27 國加 6 個關聯國
# 「Partner countries」（未關聯的第三國）就是這 33 國以外的國家，台灣屬於這一類
ERASMUS_PROGRAMME_COUNTRIES = (  # ISO 3166-1 國碼（ADR-054）
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    "IS", "LI", "NO", "MK", "RS", "TR",
)
NOT_ASSOCIATED = re.compile(r"(not|non-)\s*associated[^,.;]*", re.IGNORECASE)
PARTNER_WORD = re.compile(r"\bpartner\b", re.IGNORECASE)
PROGRAMME_WORD = re.compile(r"\bprogram(me)?\b|associated to the", re.IGNORECASE)


def erasmus_group(text: str) -> Literal["programme", "partner"] | None:
    """從截止日的說明判斷是 Erasmus+ 的哪一群申請人；兩群都寫（適用所有人）或都沒寫就回傳 None。"""
    if not re.search(r"countr|associated", text, re.IGNORECASE):
        return None  # 沒提到國家（例如「Erasmus Mundus Programme scholarship」），不是在講申請人分群
    # 「not associated to the Programme」是 partner；先拿掉這段，裡面的 Programme 才不會被當成 programme
    partner = NOT_ASSOCIATED.search(text) is not None or PARTNER_WORD.search(text) is not None
    programme = PROGRAMME_WORD.search(NOT_ASSOCIATED.sub("", text)) is not None
    if partner == programme:
        return None
    return "partner" if partner else "programme"
