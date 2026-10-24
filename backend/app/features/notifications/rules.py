"""通知的判斷規則（ADR-062、063）：截止提醒送哪一格、哪些變更值得通知、太多則時合併成摘要。

這裡都是純函式：不碰資料庫、不送訊息，同樣的輸入永遠得到同樣的結果，方便單元測試。
AI 重抽同一頁常會換個說法或漏抽，所以變更只比整理過的值（日期、數字、代號），不比原文。
"""

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
