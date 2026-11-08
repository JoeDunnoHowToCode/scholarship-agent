"""候選來源的評分與品質控制（ADR-078）：規則決定加入或排除，不另外呼叫 AI。

四條規則（docs/day-10.md 段 4）：留學國家在歐洲、碩士學位在原文找得到依據、
國籍規定沒有明確排除台灣、申請期不是一年多以前的舊資料。
"""

from dataclasses import dataclass
from datetime import datetime

# 歐洲國家的 ISO 國碼（「Claude 自行決定」第 23 點）：歐盟 27 國、歐洲經濟區、英國、瑞士，
# 以及常出現在歐洲學程裡的其他歐洲國家
EUROPE = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT",
    "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",  # 歐盟
    "IS", "LI", "NO", "GB", "CH",  # 歐洲經濟區、英國、瑞士
    "AL", "AD", "BA", "ME", "MK", "RS", "MD", "UA", "MC", "SM", "VA", "XK", "TR",  # 其他歐洲國家
})
TAIWAN = "TW"  # ADR-078：台灣人能不能申請
WEEKLY_DECISIONS = 50  # 每 7 天最多決定幾個候選（「Claude 自行決定」第 11 點）
EMPTY_LIMIT = 3  # 連續幾次抽不到有效獎學金就停用（第 11 點）


@dataclass(frozen=True)
class Facts:
    """抽取結果裡規則要看的欄位。"""

    countries: list[str]  # 留學國家的 ISO 國碼
    degrees: list[str]  # 可以讀的學位
    degrees_check: str | None  # 學位的核對結果（supported 才算有依據）
    nationality_scope: str  # all／listed／excluded／unclear
    nationalities: list[str]
    closes: list[datetime]  # 原文的截止時間（不含程式預估的）


def judge(facts: Facts, now: datetime) -> list[str]:
    """沒通過的規則（白話原因）；空清單代表全部通過，可以加入。"""
    return []  # 骨架


def next_empty(previous: int, valid: bool) -> tuple[int, bool]:
    """抽完一次後：（新的連續次數, 要不要停用）。"""
    return previous, False  # 骨架


def budget(decided_last_7_days: int) -> int:
    """這次還能決定幾個候選。"""
    return 0  # 骨架
