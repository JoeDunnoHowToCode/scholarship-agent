"""檢查頻率（ADR-058）：每個來源多久回官網看一次；日期都用台灣時間的日期。"""

from datetime import date, timedelta
from typing import Literal

Frequency = Literal["daily", "weekly", "monthly"]
WEEKLY_DAYS = 7


def frequency_for(status: str | None, stale: bool) -> Frequency:
    """依來源抽出的獎學金狀態決定多久看一次；None 代表還沒有獎學金（例如目錄頁、剛加的學程）。"""
    if status == "archived":
        # 封存的：資料過舊（最近一次真的截止日超過 24 個月）每月看，其他每週看
        return "monthly" if stale else "weekly"
    return "daily"  # 使用中，或還沒抽出獎學金


def is_due(
    frequency: Frequency,
    last_checked: date | None,
    today: date,
    recheck_from: date | None = None,
) -> bool:
    """今天要不要回官網看；last_checked 是 None 代表從沒檢查過。

    recheck_from：封存的獎學金從這天（預估開放前一個月）起才開始每週看。
    """
    if frequency == "weekly":
        if recheck_from is not None and today < recheck_from:
            return False  # 還沒到開始檢查的日子，就算從沒檢查過也不看
        return last_checked is None or today >= last_checked + timedelta(days=WEEKLY_DAYS)
    return last_checked is None or last_checked < today  # 每天：今天還沒看過就到期
