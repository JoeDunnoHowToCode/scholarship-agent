"""檢查頻率（ADR-058）：每個來源多久回官網看一次；日期都用台灣時間的日期。"""

from typing import Literal

Frequency = Literal["daily", "weekly", "monthly"]


def frequency_for(status: str | None, stale: bool) -> Frequency:
    """依來源抽出的獎學金狀態決定多久看一次；None 代表還沒有獎學金（例如目錄頁、剛加的學程）。"""
    if status == "archived":
        # 封存的：資料過舊（最近一次真的截止日超過 24 個月）每月看，其他每週看
        return "monthly" if stale else "weekly"
    return "daily"  # 使用中，或還沒抽出獎學金
