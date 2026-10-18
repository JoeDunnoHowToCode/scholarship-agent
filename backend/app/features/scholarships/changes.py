"""比對獎學金新舊資料，找出值得記錄的變更（ADR-020）：只看截止日、金額、資格、文件這些重要欄位。"""

import json
import unicodedata
from dataclasses import dataclass
from typing import Any

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
