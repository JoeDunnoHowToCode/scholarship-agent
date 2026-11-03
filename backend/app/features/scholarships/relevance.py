"""要不要重抽（ADR-079）：只看和獎學金有關的段落有沒有變。

網頁上的更新時間、最新消息每天在變，整頁的雜湊也跟著每天變；這裡只取和獎學金有關的段落算指紋，
指紋沒變、已存的原文引用也都還在，就不必請 AI 重抽。
"""

import hashlib
import re
from datetime import datetime
from typing import Literal

from app.features.documents.chunking import Chunk

# 和獎學金有關的字（英文與中文，不分大小寫）：標題或內文有其中一個，這一段就算相關
KEYWORDS = re.compile(
    r"scholarship|funding|grant|stipend|allowance|tuition|fee|deadline|application|apply|admission|"
    r"eligib|requirement|nationalit|countr|degree|intake|selection|document|amount|EUR|€|"
    r"獎學金|截止|申請|資格|名額|金額|學費|補助|國籍|學位|文件",
    re.IGNORECASE,
)

# 要不要重抽：略過（只有無關內容變了）、相關段落變了、引用不見了、太久沒重抽
Decision = Literal["skip", "relevant_changed", "quote_missing", "too_old"]


def fingerprint(chunks: list[Chunk]) -> str:
    """和獎學金有關的段落（標題或內文有關鍵字）合起來的指紋；空白不同不算變。"""
    related = [
        " ".join(chunk.text.split())  # 正規化：連續空白、換行都當成一個空白
        for chunk in chunks
        if KEYWORDS.search(" ".join(chunk.heading_path)) or KEYWORDS.search(chunk.text)
    ]
    return hashlib.sha256("\n".join(related).encode()).hexdigest()


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
