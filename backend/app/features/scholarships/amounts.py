"""獎學金的金額（第 9 天，ADR-070）：每個金額一筆，附用途與原文引用；程式核對引用與數字，產生列表與文字用的說明。"""

import math
import re
import unicodedata

import pycountry

from app.features.documents.checks import quote_in_source, quote_in_table_text
from app.features.scholarships.schemas import AmountDraft

# 中文單位：「1 萬 6 千」「3 萬」「1.6 萬」「5 千」（教育部簡章的寫法）
_WAN = re.compile(r"(\d+(?:\.\d+)?)\s*[萬万](?:\s*(\d+)\s*千)?")
_QIAN = re.compile(r"(\d+(?:\.\d+)?)\s*千")
# 一串數字，中間可以夾逗號或點，例如 1,400、5.613,10、2.5
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*")


def _parse(token: str) -> float | None:
    """1,400 → 1400；5,613.10 → 5613.1；2.5 → 2.5。最後一段只有 1–2 位數的是小數點，其他每段要剛好 3 位數（千分位）。"""
    parts = re.split(r"[.,]", token)
    if len(parts) == 1:
        return float(token)
    whole, decimal = (parts[:-1], parts[-1]) if len(parts[-1]) in (1, 2) else (parts, "")
    if any(len(part) != 3 for part in whole[1:]):
        return None  # 不是金額的寫法，例如 1.2.3
    return float("".join(whole) + (f".{decimal}" if decimal else ""))


def numbers_in(text: str) -> set[float]:
    """文字裡寫到的所有數字；用來確認引用裡真的有那個金額。"""
    text = unicodedata.normalize("NFKC", text)  # 全形數字與標點換成半形
    found: set[float] = set()

    def wan(match: re.Match[str]) -> str:
        extra = float(match[2]) * 1000 if match[2] else 0.0
        found.add(round(float(match[1]) * 10000 + extra, 2))  # round：1.6 × 10000 的浮點誤差
        return " "  # 換掉這一段，下面才不會把「1 萬 6 千」裡的 1、6 也當成數字

    def qian(match: re.Match[str]) -> str:
        found.add(round(float(match[1]) * 1000, 2))
        return " "

    text = _QIAN.sub(qian, _WAN.sub(wan, text))
    for token in _TOKEN.findall(text):
        number = _parse(token)
        if number is not None:
            found.add(number)
    return found


def amount_status(amount: AmountDraft, source: str) -> str:
    """金額的核對結果，只用程式、不另外問 AI（docs/day-09.md「Claude 自行決定」第 21 點）：
    supported、no_evidence、invalid_currency、quote_not_found、number_not_in_quote。"""
    if not amount.evidence:
        return "no_evidence"
    if pycountry.currencies.get(alpha_3=amount.currency.upper()) is None:
        return "invalid_currency"
    # 和驗證者一樣：表格的字被交錯排列時，允許引用切成幾截就近出現
    if not (quote_in_source(amount.evidence, source) or quote_in_table_text(amount.evidence, source)):
        return "quote_not_found"
    if not any(math.isclose(number, amount.value) for number in numbers_in(amount.evidence)):
        return "number_not_in_quote"
    return "supported"
