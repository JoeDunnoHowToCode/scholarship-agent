"""模型評估指令（ADR-098）：同一批來源、同一份已存的快照，讓指定的模型各抽幾次，不寫回資料庫。

用法：
  uv run python -m app.features.evaluation.run --models gemini-3.5-flash-lite gemini-3.1-flash-lite --rounds 2 --max-cost 80
  uv run python -m app.features.evaluation.run --tally 2026-11-10    讀你填好的抽查清單，補進報告

原始結果與抽查清單在 backend/data/eval/<日期>/（含各網站的原文引用，不進 git）；報告只有數字，在 docs/eval/<日期>.md。
"""

from typing import Any

from app.features.scholarships.schemas import ScholarshipDraft

SEED = 11  # 固定的亂數種子：每次挑到同一批 Erasmus 學程
ERASMUS_SAMPLE = 40


def pick_sample(non_erasmus: list[int], erasmus: list[int], n: int = ERASMUS_SAMPLE, seed: int = SEED) -> list[int]:
    """評估樣本：所有非 Erasmus 的來源，加上用固定種子挑的 n 個 Erasmus 學程。"""
    return []  # 骨架


def record_of(
    source: dict[str, Any], model: str, round_no: int, verified: ScholarshipDraft | None,
    extracted: dict[str, Any] | None, seconds: float, cost_usd: float, error: str | None,
) -> dict[str, Any]:
    """一次抽取的紀錄（格式見 metrics.py）：只留比較要用的欄位、引用與核對結果。"""
    return {}  # 骨架


def report_markdown(results: dict[str, list[list[dict[str, Any]]]], date: str) -> str:
    """報告（只有數字，進 git）：results 是 {模型: [第 1 次的紀錄, 第 2 次的紀錄, …]}。"""
    return ""  # 骨架


def disagreements_markdown(items: list[dict[str, Any]], first: str, second: str) -> str:
    """抽查清單（含原文引用，不進 git）：每一筆留一行「誰對：」給你填 A、B、都對或都錯。"""
    return ""  # 骨架
