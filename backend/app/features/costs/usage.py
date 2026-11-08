"""費用計算（ADR-013、049、089）：本月從什麼時候算起、有沒有超過每月上限。"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

NTD_PER_USD = 32  # 和其他指令一樣的粗估匯率
TAIPEI = ZoneInfo("Asia/Taipei")  # 和每天檢查的日期（runs.local_date）一致


def month_start(now: datetime) -> datetime:
    """本月第一刻（以台灣時間的月份計算），回傳 UTC 時間。"""
    local = now.astimezone(TAIPEI)
    first = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first.astimezone(UTC)


def over_cap(spent_usd: float, cap_ntd: float) -> bool:
    """本月已花的錢有沒有達到上限（新台幣）。"""
    return spent_usd * NTD_PER_USD >= cap_ntd
