"""評估的指標（ADR-098）：都是純函式，輸入是每一次抽取的紀錄（JSON 能存的 dict）。

一筆紀錄：{"source_id", "name", "url", "model", "round", "ok", "error", "seconds", "cost_usd",
          "fields": {"deadlines": [...], "nationality": str, "degrees": [...], "amounts": [...]},
          "evidence": {欄位: 引用}, "verification": {"nationality", "degrees", "deadlines": [...], "amounts": [...]},
          "issues": 規則問題數}
"""

from typing import Any

Record = dict[str, Any]
FIELDS = ("deadlines", "nationality", "degrees", "amounts")  # 抽查也照這個順序挑


def grounded(records: list[Record]) -> dict[str, float]:
    """各欄位的有根據率：原文引用撐得起的比例。"""
    return dict.fromkeys(FIELDS, 0.0)  # 骨架


def incomplete(records: list[Record]) -> float:
    """截止日不完整率：抽到了但缺年份之類、沒辦法建成申請期的比例。"""
    return 0.0  # 骨架


def agreement(first: list[Record], second: list[Record]) -> dict[str, float]:
    """兩組結果（同一模型兩次＝穩定度；兩個模型＝一致率）每個欄位一樣的比例，只算兩邊都抽成功的來源。"""
    return dict.fromkeys((*FIELDS, "all"), 0.0)  # 骨架


def disagreements(first: list[Record], second: list[Record], limit: int = 10) -> list[dict[str, Any]]:
    """兩組結果不一樣的地方，給人抽查：每個來源最多一筆，最多 limit 筆；兩邊都沒抽到的不算。"""
    return []  # 骨架


def tally(text: str) -> dict[str, int]:
    """讀抽查清單裡填好的「誰對：」，數 A、B、都對、都錯各幾筆；沒填的算未填。"""
    return {}  # 骨架
