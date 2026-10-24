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


# 表格引用的每一截至少幾個字、下一截要在上一截結尾後幾個字內出現
MIN_FRAGMENT = 6
FRAGMENT_WINDOW = 300


def quote_in_table_text(quote: str, source: str) -> bool:
    """表格版的引用核對：pdfplumber 會把表格左右兩欄的字交錯排在一起，
    所以允許引用被切成幾截，但每一截至少 6 個字、依序出現，而且下一截就在附近。"""
    remaining = _normalize(quote)
    normalized_source = _normalize(source)
    if not remaining:
        return False
    position = 0
    first = True
    while remaining:
        # 第一截可以在原文任何地方；之後每一截只在上一截結尾後的附近找
        region = normalized_source[position:] if first else normalized_source[
            position : position + FRAGMENT_WINDOW + len(remaining)
        ]
        # 從最長的開頭往短的試，找到最長、而且原文裡有的那一截。
        # 每一截至少 6 個字；只有第一截在整句不到 6 個字時例外。最後剩不到 6 個字就算找不到，
        # 不然「15」的「5」只要附近有別的「5」就會被當成找到（第 8 天發現）
        shortest = min(MIN_FRAGMENT, len(remaining)) if first else MIN_FRAGMENT
        for length in range(len(remaining), shortest - 1, -1):
            found = region.find(remaining[:length])
            if found != -1 and (first or found <= FRAGMENT_WINDOW):
                break
        else:
            return False
        position += found + length
        remaining = remaining[length:]
        first = False
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
