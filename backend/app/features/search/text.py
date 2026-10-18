"""要變成向量的文字：段落標題和獎學金簡介。"""

from typing import Any


def chunk_title(heading_path: list[str]) -> str:
    """段落所在的標題路徑，例如「簡章 > 四、獎助類別及名額」；空白的標題略過。"""
    return " > ".join(heading.strip() for heading in heading_path if heading.strip())


# 簡介裡每一行的欄位和中文標籤，依這個順序輸出
PROFILE_LABELS = {
    "name": "名稱",
    "provider": "提供單位",
    "countries": "國家",
    "degrees": "學位",
    "fields": "領域",
    "coverage": "補助內容",
    "amount": "金額",
    "other_eligibility": "資格",
    "language_requirements": "語言要求",
}


def scholarship_profile(fields: dict[str, Any]) -> str:
    """把獎學金欄位寫成「標籤：值」一行一行的文字；沒填（None、空字串、空清單）的欄位略過。"""
    lines = []
    for key, label in PROFILE_LABELS.items():
        value = fields.get(key)
        if isinstance(value, list):
            value = ", ".join(value)
        if value:
            lines.append(f"{label}：{value}")
    return "\n".join(lines)
