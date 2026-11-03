"""要不要重抽（ADR-079）：只看和獎學金有關的段落有沒有變。

網頁上的更新時間、最新消息每天在變，整頁的雜湊也跟著每天變；這裡只取和獎學金有關的段落算指紋，
指紋沒變、已存的原文引用也都還在，就不必請 AI 重抽。
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Literal

from app.features.documents.chunking import Chunk
from app.features.scholarships.changes import _found

# 上次真的抽取超過這麼久，就整份重抽一次（安全網：萬一關鍵字漏掉了真的變更）
FULL_REEXTRACT_AFTER = timedelta(days=30)

# 和獎學金有關的字（英文與中文，不分大小寫）：標題或內文有其中一個，這一段就算相關
KEYWORDS = re.compile(
    r"scholarship|funding|grant|stipend|allowance|tuition|fee|deadline|application|apply|admission|"
    r"eligib|requirement|nationalit|countr|degree|intake|selection|document|amount|EUR|€|"
    r"獎學金|截止|申請|資格|名額|金額|學費|補助|國籍|學位|文件",
    re.IGNORECASE,
)

# 每次載入都會換的東西，算指紋前先拿掉：email（有些網站每次都換防垃圾信的代碼）、UUID、
# 16 個字以上的十六進位亂碼、ISO 格式的時間戳記（例如 2026-10-28T14:17:37+01:00）。一般的日期不拿掉
PER_LOAD = re.compile(
    r"\S+@\S+"
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|\b[0-9a-f]{16,}\b"
    r"|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:\d{2}|Z)?",
    re.IGNORECASE,
)

# 要不要重抽：略過（只有無關內容變了）、相關段落變了、引用不見了、太久沒重抽
Decision = Literal["skip", "relevant_changed", "quote_missing", "too_old"]


def fingerprint(chunks: list[Chunk]) -> str:
    """和獎學金有關的段落（標題或內文有關鍵字）合起來的指紋；空白不同不算變。"""
    related = [
        " ".join(PER_LOAD.sub("", chunk.text).split())  # 正規化：拿掉每次載入都會換的東西，空白合成一個
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
    """快照變了之後，要不要請 AI 重抽。

    quotes 是已存的原文引用（截止日、國籍、學位、金額）；有一句在新版找不到，代表相關內容可能變了。
    """
    if last_extracted is None or now - last_extracted >= FULL_REEXTRACT_AFTER:
        return "too_old"
    if old_fingerprint != new_fingerprint:
        return "relevant_changed"
    # 用和驗證者一樣的比對方式找引用（_found 回傳 0 代表完全找不到）
    if any(_found(quote, new_text) == 0 for quote in quotes):
        return "quote_missing"
    return "skip"
