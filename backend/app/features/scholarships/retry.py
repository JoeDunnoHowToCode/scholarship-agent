"""核對沒過就把錯誤拋回 AI 重抽一次（ADR-111）：哪些狀態要重抽、錯誤訊息怎麼寫、怎麼比較兩次的結果。"""

from typing import Any

from app.features.scholarships.schemas import AmountDraft, ScholarshipDraft
from app.features.scholarships.verify import claims

# 值得重抽的狀態與白話原因。不在這裡的（incomplete、empty、conflict、supported、catalogue）不重抽：
# 年份交給程式推算（ADR-110）、沒有值、長文件各節說法不同，重抽也不會變好
REASONS = {
    "not_supported": "核對的 AI 判斷引用撐不起這個值",
    "quote_not_found": "引用不在原文裡，要逐字複製原文",
    "no_evidence": "沒有附引用",
    "year_not_in_quote": "年份不在引用裡，原文沒寫年份就留空",
    "closes_before_opens": "截止日早於開放日",
    "degree_not_in_quote": "引用裡沒有這個學位",
    "number_not_in_quote": "金額或百分比不在引用裡",
    "invalid_currency": "幣別不是 ISO 4217 三碼",
    "period_mismatch": "引用寫每學期，卻存成每年",
}
# 欄位對應標準（docs/extraction-standard.md）的哪一節
STANDARD = {"nationality": "4", "degrees": "6", "deadline": "2", "amount": "3", "offered": "5.1", "missed_date": "2"}


def amount_value(amount: AmountDraft) -> str:
    if amount.value is not None:
        number = f"{amount.value:g} {amount.currency}"
    else:
        number = f"{amount.percent:g}%" if amount.percent is not None else "沒有數字"
    return f"{number}，期間 {amount.period}，用途 {amount.kind}"


def _failed(status: dict[str, Any]) -> list[tuple[str, int | None, str]]:
    """（欄位, 第幾個, 狀態）：值得重抽的那些。"""
    found: list[tuple[str, int | None, str]] = []
    for field in ("nationality", "degrees", "offered"):
        if status.get(field) in REASONS:
            found.append((field, None, status[field]))
    for name, key in (("deadline", "deadlines"), ("amount", "amounts")):
        found += [(name, index, s) for index, s in enumerate(status.get(key, [])) if s in REASONS]
    if status.get("missed_date"):
        found.append(("missed_date", None, "missed_date"))  # ADR-119：原文有日期，抽取一個都沒有
    return found


def problems(draft: ScholarshipDraft, status: dict[str, Any]) -> list[str]:
    """沒過核對、值得重抽的欄位，每個一行錯誤訊息；全部通過就是空清單。"""
    claimed = claims(draft)
    labels = {"nationality": "國籍", "degrees": "學位", "offered": "今年有沒有開"}
    lines = []
    for field, index, state in _failed(status):
        if field == "missed_date":
            lines.append(
                f"- 截止日：上次沒有抽出任何申請日期，但原文有「{status['missed_date']}」；"
                f"照原文寫進 windows，年份沒寫就留空（標準 {STANDARD[field]}）"
            )
            continue
        if field == "amount" and index is not None:
            amount = draft.amounts[index]
            label, value, quote = f"金額 {index + 1}", amount_value(amount), amount.evidence
        elif field == "deadline" and index is not None:
            label, (value, quote) = f"截止日 {index + 1}", claimed[f"deadline:{index}"]
        else:
            label, (value, quote) = labels[field], claimed[field]
        lines.append(f"- {label}：上次填「{value}」，引用「{quote or ''}」；{REASONS[state]}（標準 {STANDARD[field]}）")
    return lines


def failures(status: dict[str, Any]) -> int:
    """值得重抽的欄位有幾個（國籍、學位、每個申請期、每筆金額、今年有沒有開）。"""
    return len(_failed(status))


def fields(status: dict[str, Any]) -> list[str]:
    """重抽了哪些欄位（記在 extracted.retry）：國籍、學位、今年有沒有開用欄位名，申請期與金額寫成 deadline:0、amount:1。"""
    return [field if index is None else f"{field}:{index}" for field, index, _ in _failed(status)]
