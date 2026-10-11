"""用 pdfplumber 抽出的原始文字，檢查 Gemini 的 PDF 轉錄稿有沒有寫錯（ADR-037）。"""

import re
import unicodedata

# 刪節號：三個半形點，或一個「…」
ELLIPSIS = re.compile(r"\.\.\.|…")

# 數字：可以帶千分位逗號或小數點，例如 16,000、25.5
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _normalize(text: str) -> str:
    """全形轉半形（NFKC），再去掉所有空白和換行。"""
    return "".join(unicodedata.normalize("NFKC", text).split())


def quote_in_source(quote: str, source: str) -> bool:
    """引用是否真的出現在原文；引用裡用刪節號省略的部分，每一截都要依序出現。"""
    parts = [part for part in ELLIPSIS.split(_normalize(quote)) if part]
    if not parts:
        return False
    normalized_source = _normalize(source)
    position = 0
    for part in parts:
        found = normalized_source.find(part, position)
        if found == -1:
            return False
        # 下一截要從這一截的結尾之後開始找，才能確認順序
        position = found + len(part)
    return True


def unverified_numbers(transcript: str, raw: str) -> list[str]:
    """列出轉錄稿裡、原始文字找不到的數字（逗號不算，所以 1,400 和 1400 視為相同）。"""
    numbers = [
        number.replace(",", "")
        for number in NUMBER.findall(unicodedata.normalize("NFKC", transcript))
    ]
    normalized_raw = _normalize(raw).replace(",", "")
    missing = [number for number in numbers if number not in normalized_raw]
    # dict.fromkeys 去掉重複，同時保留第一次出現的順序
    return list(dict.fromkeys(missing))
