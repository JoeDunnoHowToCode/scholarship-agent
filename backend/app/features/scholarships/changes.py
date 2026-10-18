"""比對獎學金新舊資料，找出值得記錄的變更（ADR-020）：只看截止日、金額、資格、文件這些重要欄位。"""

from typing import Any


def diff_important(old: dict[str, Any], new: dict[str, Any]) -> list[Any]:
    """回傳重要欄位的變更清單；目前還沒有比對任何欄位。"""
    return []
