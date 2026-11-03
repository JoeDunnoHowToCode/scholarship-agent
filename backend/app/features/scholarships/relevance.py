"""要不要重抽（ADR-079）：只看和獎學金有關的段落有沒有變。

網頁上的更新時間、最新消息每天在變，整頁的雜湊也跟著每天變；這裡只取和獎學金有關的段落算指紋，
指紋沒變、已存的原文引用也都還在，就不必請 AI 重抽。
"""

from datetime import datetime
from typing import Literal

from app.features.documents.chunking import Chunk

# 要不要重抽：略過（只有無關內容變了）、相關段落變了、引用不見了、太久沒重抽
Decision = Literal["skip", "relevant_changed", "quote_missing", "too_old"]


def fingerprint(chunks: list[Chunk]) -> str:
    """和獎學金有關的段落（標題或內文有關鍵字）合起來的指紋；空白不同不算變。"""
    return ""


def decide(
    old_fingerprint: str,
    new_fingerprint: str,
    quotes: list[str],
    new_text: str,
    last_extracted: datetime | None,
    now: datetime,
) -> Decision:
    """快照變了之後，要不要請 AI 重抽。"""
    return "skip"
