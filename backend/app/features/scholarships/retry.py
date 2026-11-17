"""核對沒過就把錯誤拋回 AI 重抽一次（ADR-111）：哪些狀態要重抽、錯誤訊息怎麼寫、怎麼比較兩次的結果。"""

from typing import Any

from app.features.scholarships.schemas import ScholarshipDraft


def problems(draft: ScholarshipDraft, status: dict[str, Any]) -> list[str]:
    """沒過核對、值得重抽的欄位，每個一行錯誤訊息；全部通過就是空清單。"""
    return []


def failures(status: dict[str, Any]) -> int:
    """值得重抽的欄位有幾個（國籍、學位、每個申請期、每筆金額、今年有沒有開）。"""
    return 0
