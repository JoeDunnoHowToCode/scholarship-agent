"""抽取結果的程式檢查（ADR-045）：不花 AI 費用，擋下模型每次都會犯的錯。"""

import re
import unicodedata

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
