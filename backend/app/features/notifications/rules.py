"""通知的判斷規則（ADR-062、063）：截止提醒送哪一格、哪些變更值得通知、太多則時合併成摘要。

這裡都是純函式：不碰資料庫、不送訊息，同樣的輸入永遠得到同樣的結果，方便單元測試。
AI 重抽同一頁常會換個說法或漏抽，所以變更只比整理過的值（日期、數字、代號），不比原文。
"""

import re
from typing import Any

from app.core.notify.base import Notification

# 截止前幾天提醒（docs/day-08.md「Claude 自行決定」第 6 點），由大到小
REMINDER_DAYS = (30, 14, 7, 3, 1)


def reminder_bucket(days_left: int, sent: set[int]) -> int | None:
    """剩 days_left 天時要送哪一格截止提醒；sent 是這個截止日已經送過的格子。

    每天的檢查不一定每天都跑（電腦沒網路），所以只送「現在這一格」：
    錯過的大格子直接跳過、不補送；這一格送過了就回傳 None。
    """
    if days_left < 0 or days_left > max(REMINDER_DAYS):
        return None  # 已經截止，或還早（超過 30 天）
    # 現在這一格：天數還沒低於它的格子裡最小的，例如剩 12 天是「14 天」那格
    bucket = min(day for day in REMINDER_DAYS if day >= days_left)
    return None if bucket in sent else bucket


# 國籍資格的代號換成中文（ADR-043）
SCOPE_NAMES = {
    "all": "不限國籍",
    "listed": "只限列出的國家",
    "excluded": "列出的國家以外都可以",
    "unclear": "原文沒寫",
}
# 學位的代號換成中文；寫出來時照這個順序
DEGREE_NAMES = {"bachelor": "學士", "master": "碩士", "phd": "博士"}


def _closing_dates(windows: list[dict[str, Any]]) -> set[str]:
    """申請窗口裡年、月、日都有的截止日，寫成 2027-01-15；標籤或引用換了說法不影響。"""
    return {
        f"{w['closes_year']:04d}-{w['closes_month']:02d}-{w['closes_day']:02d}"
        for w in windows
        if w["closes_year"] and w["closes_month"] and w["closes_day"]
    }


def _degree_names(degrees: list[str]) -> str:
    """學位代號換成中文，照學士、碩士、博士的順序；空清單寫「原文沒寫」。"""
    return "、".join(name for code, name in DEGREE_NAMES.items() if code in degrees) or "原文沒寫"


def amount_numbers(text: str | None) -> set[str]:
    """金額文字裡的數字，例如「€1,400 per month」→ {"1400"}；只比數字，換個寫法不算變更。

    千分位的逗號拿掉；點後面剛好三位數也當千分位（歐洲寫法 1.400 → 1400），其他的點是小數點（2.5 照舊）。
    """
    return {
        # \.(?=\d{3}(?!\d))：後面剛好接三位數（第四個字不是數字）的點
        re.sub(r"\.(?=\d{3}(?!\d))", "", number.replace(",", ""))
        # \d+(?:[.,]\d+)*：一串數字，中間可以夾逗號或點，例如 1,400、1.200.000、2.5
        for number in re.findall(r"\d+(?:[.,]\d+)*", text or "")
    }


def describe_change(field: str, old: Any, new: Any) -> str | None:
    """一筆變更值不值得通知：值得就回傳一句中文說明，不值得就回傳 None。

    old、new 是變更紀錄裡原本的值（changes.Change）。只比整理過的值：
    AI 換了說法不算變更；有一邊變成空的，多半是 AI 這次漏抽，也不通知。
    """
    if field == "windows":
        # 舊資料可能還沒有申請窗口這個欄位（None），當成沒有截止日
        before, after = _closing_dates(old or []), _closing_dates(new or [])
        # 舊的沒有截止日是新的一屆（另外通知）；新的沒有多半是 AI 漏抽
        if not before or not after or before == after:
            return None
        return f"截止日：{'、'.join(sorted(before))} → {'、'.join(sorted(after))}"
    if field == "nationality_scope":
        if old == new:
            return None
        return f"國籍資格：{SCOPE_NAMES[old]} → {SCOPE_NAMES[new]}"
    if field == "nationalities":
        # 國碼不分大小寫
        before, after = {code.upper() for code in old}, {code.upper() for code in new}
        # 有一邊是空清單：AI 有時沒把 EU 這種集合展開成國碼（docs/adr.md 待決定 #52）
        if not before or not after or before == after:
            return None
        parts: list[str] = []
        if after - before:
            parts.append(f"新增 {'、'.join(sorted(after - before))}")
        if before - after:
            parts.append(f"移除 {'、'.join(sorted(before - after))}")
        return f"國籍清單：{'；'.join(parts)}"
    if field == "degrees":
        if not new or set(old) == set(new):
            return None  # 新的是空清單：多半是 AI 漏抽
        return f"可讀學位：{_degree_names(old)} → {_degree_names(new)}"
    if field == "amount":
        before, after = amount_numbers(old), amount_numbers(new)
        # 有一邊沒有數字（例如「全額補助」、或 AI 漏抽）：比不出來，不通知
        if not before or not after or before == after:
            return None
        return f"金額：{old[:60]} → {new[:60]}"  # 原文太長只留前 60 個字
    if field == "requirements":
        # 只通知新增的文件種類；變少或變空白，多半是 AI 這次沒抽到
        added = {item["doc_type"] for item in new} - {item["doc_type"] for item in old}
        if not added:
            return None
        return f"新增文件要求：{'、'.join(sorted(added))}"
    return None  # 其他欄位不通知


BUNDLE_LIMIT = 5  # 一次超過這麼多則就合併成摘要（docs/day-08.md「Claude 自行決定」第 9 點）
# 摘要裡照這個順序分組，每組先寫標題；不在這裡的類型放最後的【其他】
DIGEST_HEADERS = {
    "deadline": "【截止提醒】",
    "new_cycle": "【新年度開放】",
    "new_scholarship": "【新獎學金】",
    "change": "【資料變更】",
}


def bundle(notifications: list[Notification]) -> list[Notification]:
    """一次要送的通知超過 5 則，就合併成一則摘要，手機才不會一直響。

    系統通知（例如斷路器打開）不合併、排最前面；其他的 5 則以內就照原樣各送各的。
    """
    system = [n for n in notifications if n.kind == "system"]
    others = [n for n in notifications if n.kind != "system"]
    if len(others) <= BUNDLE_LIMIT:
        return system + others
    lines: list[str] = []
    for kind, header in DIGEST_HEADERS.items():
        titles = [n.title for n in others if n.kind == kind]  # 同一組裡照原本的順序
        if titles:
            lines += [header, *titles]
    rest = [n.title for n in others if n.kind not in DIGEST_HEADERS]
    if rest:
        lines += ["【其他】", *rest]
    # 摘要只列標題，沒有單一個連結
    digest = Notification(kind="digest", title=f"今天有 {len(others)} 則獎學金通知", lines=tuple(lines), url=None)
    return [*system, digest]
