"""比對獎學金新舊資料，找出值得記錄的變更（ADR-020）：只看截止日、金額、資格、文件這些重要欄位。"""

import json
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.features.documents.checks import quote_in_source, quote_in_table_text

# 只有這些欄位變了才記錄；結果也照這個順序排
IMPORTANT_FIELDS = (
    "amount",
    "coverage",
    "nationality_scope",
    "nationalities",
    "degrees",
    "language_requirements",
    "other_eligibility",
    "windows",
    "categories",
    "requirements",
)


@dataclass(frozen=True)
class Change:
    """一筆變更：哪個欄位、舊值、新值（都是原本的樣子，沒有正規化）。"""

    field: str
    old: Any
    new: Any


def _normalize(value: Any) -> Any:
    """把只是寫法不同的值變成一樣，比對時才不會誤報。"""
    if isinstance(value, str):
        # 全形轉半形、不分大小寫、連續空白變一個；空字串當成沒有值
        text = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
        return text or None
    if isinstance(value, list):
        # 清單順序不重要：每一項正規化後，用固定的方式排序
        items = [_normalize(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    if isinstance(value, dict):
        # 引用（evidence）換句話說不算變更，直接不比
        return {key: _normalize(item) for key, item in value.items() if not key.endswith("evidence")}
    return value  # 數字、布林、None 照原樣比


def diff_important(old: dict[str, Any], new: dict[str, Any]) -> list[Change]:
    """回傳重要欄位的變更清單，依 IMPORTANT_FIELDS 的順序；沒變就是空清單。"""
    return [
        Change(field, old.get(field), new.get(field))
        for field in IMPORTANT_FIELDS
        if _normalize(old.get(field)) != _normalize(new.get(field))
    ]


# 會推播的欄位（ADR-064）要核對原文：欄位 → 抽取結果裡支持它的引用（截止日的引用在每個申請窗口裡）
QUOTE_KEYS = {
    "nationality_scope": "nationality_evidence",
    "nationalities": "nationality_evidence",
    "degrees": "degrees_evidence",
    "windows": "evidence",
}


def _quotes(field: str, extracted: dict[str, Any]) -> list[str]:
    """這個欄位的原文引用；截止日每個申請窗口各一句。沒附引用的略過。"""
    key = QUOTE_KEYS[field]
    if field == "windows":
        found = [window.get(key) for window in extracted.get("windows") or []]
    else:
        found = [extracted.get(key)]
    return [quote for quote in found if quote]


def _in(quote: str, text: str) -> bool:
    # 和驗證者一樣：表格的字被交錯排列時，允許引用切成幾截就近出現
    return quote_in_source(quote, text) or quote_in_table_text(quote, text)


def website_changed(field: str, old: dict[str, Any], new: dict[str, Any], old_text: str, new_text: str) -> bool:
    """官網這部分真的改了沒有（ADR-064）：有一句引用只出現在新版網頁，或只出現在舊版網頁。

    AI 重抽同一份原文時常挑不同的句子；那些句子新舊兩版都有，不算變更。
    old_text、new_text 是新舊兩版網頁的原文（和抽取時核對用的一樣）。
    """
    added = any(not _in(quote, old_text) for quote in _quotes(field, new))
    removed = any(not _in(quote, new_text) for quote in _quotes(field, old))
    return added or removed
