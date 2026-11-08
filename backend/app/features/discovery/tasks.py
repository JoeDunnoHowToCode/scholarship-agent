"""agent 的任務內容（ADR-083）：交給 agent 的資料只有這裡組出來的文字。

個人資料只能經過 applicant_text（科系、想讀的領域，ADR-055、087）；國籍、想去的國家都不給 agent。
"""

from datetime import date

from app.features.profiles.models import Profile

# 搜尋補漏的範圍用規格的範圍，不用個人資料裡「想去的國家」（「Claude 自行決定」第 10 點）
SCOPE = "英國、北歐（瑞典、芬蘭、丹麥、挪威、冰島）、其他歐洲國家"


def search_task(profile: Profile | None, today: date) -> str:
    """搜尋補漏的任務：範圍、學位、年度，加上科系與領域。"""
    return ""  # 骨架
