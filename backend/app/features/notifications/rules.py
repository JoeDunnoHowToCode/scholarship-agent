"""通知的判斷規則（ADR-062、063）：截止提醒送哪一格、哪些變更值得通知、太多則時合併成摘要。

這裡都是純函式：不碰資料庫、不送訊息，同樣的輸入永遠得到同樣的結果，方便單元測試。
AI 重抽同一頁常會換個說法或漏抽，所以變更只比整理過的值（日期、代號），不比原文。
"""

import re
from datetime import date
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


def cycle_year(intake: str | None, closes_year: int) -> int:
    """這個截止日屬於哪一屆：入學年度裡第一個四位數年份（2027/28 → 2027）；沒寫入學年度就用截止的年份。"""
    match = re.search(r"\d{4}", intake or "")
    return int(match[0]) if match else closes_year


def _closing_dates(windows: list[dict[str, Any]]) -> dict[int, set[str]]:
    """依「哪一屆」分組的截止日（年、月、日都有的才算），寫成 2027-01-15；標籤或引用換了說法不影響。"""
    dates: dict[int, set[str]] = {}
    for w in windows:
        if w["closes_year"] and w["closes_month"] and w["closes_day"]:
            year = cycle_year(w.get("intake"), w["closes_year"])
            dates.setdefault(year, set()).add(f"{w['closes_year']:04d}-{w['closes_month']:02d}-{w['closes_day']:02d}")
    return dates


def _degree_names(degrees: list[str]) -> str:
    """學位代號換成中文，照學士、碩士、博士的順序；空清單寫「原文沒寫」。"""
    return "、".join(name for code, name in DEGREE_NAMES.items() if code in degrees) or "原文沒寫"


def describe_change(field: str, old: Any, new: Any, today: date | None = None) -> str | None:
    """一筆變更值不值得通知：值得就回傳一句中文說明，不值得就回傳 None。

    old、new 是變更紀錄裡原本的值（changes.Change）。只比整理過的值：
    AI 換了說法不算變更；有一邊變成空的，多半是 AI 這次漏抽，也不通知。
    today 是台灣的今天：新的截止日都已經過去就不通知（ADR-065）。每天產生事件時一定會給，只有測試其他規則時省略。
    """
    if field == "windows":
        # 舊資料可能還沒有申請窗口這個欄位（None），當成沒有截止日
        old_by_year, new_by_year = _closing_dates(old or []), _closing_dates(new or [])
        # 只比兩邊都有的那幾屆：只有新的才有的一屆是新年度開放（另外通知）；
        # 舊的沒有截止日也一樣；新的沒有多半是 AI 漏抽
        shared = sorted(set(old_by_year) & set(new_by_year))
        changed = [year for year in shared if old_by_year[year] != new_by_year[year]]
        if not changed:
            return None
        old_dates = sorted(day for year in changed for day in old_by_year[year])
        new_dates = sorted(day for year in changed for day in new_by_year[year])
        if today is not None and all(day < today.isoformat() for day in new_dates):
            return None  # 新的截止日都已經過去：多半是 AI 抽到舊一屆的句子（ADR-065）
        return f"截止日：{'、'.join(old_dates)} → {'、'.join(new_dates)}"
    if field == "nationality_scope":
        # 空值或不認得的值（舊資料）：比不出來，不通知
        if old == new or old not in SCOPE_NAMES or new not in SCOPE_NAMES:
            return None
        if new == "unclear":
            return None  # 變成「原文沒寫」：官網沒改，只是 AI 這次沒抽到（ADR-064）
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
    return None  # 其他欄位（金額、文件要求等）不通知：不影響能不能申請（ADR-064）


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
