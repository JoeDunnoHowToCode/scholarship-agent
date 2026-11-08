"""費用計算（ADR-013、049、089）：本月從什麼時候算起、有沒有超過每月上限。"""

from datetime import datetime

NTD_PER_USD = 32  # 和其他指令一樣的粗估匯率


def month_start(now: datetime) -> datetime:
    """本月第一刻（以台灣時間的月份計算），回傳 UTC 時間。"""
    return now  # 骨架


def over_cap(spent_usd: float, cap_ntd: float) -> bool:
    """本月已花的錢有沒有達到上限（新台幣）。"""
    return False  # 骨架
