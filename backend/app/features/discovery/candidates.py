"""候選來源的評分與品質控制（ADR-078）：規則決定加入或排除，不另外呼叫 AI。

四條規則（docs/day-10.md 段 4）：留學國家在歐洲、碩士學位在原文找得到依據、
國籍規定沒有明確排除台灣、申請期不是一年多以前的舊資料。
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.features.matching.checks import nationality_check

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
TOO_OLD = timedelta(days=365)  # 最晚的截止日比現在早這麼久，就當成舊資料


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
    """沒通過的規則（白話原因）；空清單代表全部通過，可以加入。

    原文沒寫的（國籍、申請期）不拿來排除：spec 規定全部列出、不過濾，評分時會標「待確認」。
    """
    reasons = []
    if not EUROPE.intersection(code.upper() for code in facts.countries):
        reasons.append("留學國家不在歐洲")
    if "master" not in facts.degrees or facts.degrees_check != "supported":
        reasons.append("原文沒有可核對的碩士學位")
    if nationality_check(TAIWAN, facts.nationality_scope, facts.nationalities) == "fail":
        reasons.append("國籍規定排除台灣")
    if facts.closes and max(facts.closes) < now - TOO_OLD:
        reasons.append("申請期都是一年多以前的")
    return reasons


def next_empty(previous: int, valid: bool) -> tuple[int, bool]:
    """抽完一次後：（新的連續次數, 要不要停用）。"""
    if valid:
        return 0, False
    count = previous + 1
    return count, count >= EMPTY_LIMIT


def budget(decided_last_7_days: int) -> int:
    """這次還能決定幾個候選。"""
    return max(0, WEEKLY_DECISIONS - decided_last_7_days)


SIMILAR = 0.96  # 語意相似度到這裡就算重複（11-09 實測：不重複的最高 0.939，重複的 0.971–0.981）


@dataclass(frozen=True)
class Brief:
    """比對是不是同一個獎學金時要看的欄位。"""

    provider: str  # 已正規化（小寫、去標點）；空字串代表沒抽到
    countries: frozenset[str]
    closes: frozenset[str]  # 原文的截止日（YYYY-MM-DD），不含程式預估的
    embedding: list[float] | None


Verdict = Literal["duplicate", "different", "unclear"]


def same_scholarship(new: Brief, old: Brief) -> Verdict:
    """規則比對（11-09 使用者選 E＋D）：判斷不了的回 unclear，交給 AI 讀內容（D）。

    只比同一個提供者：提供者不同，或沒抽到提供者，就當成不同的獎學金（不冒險合併）。
    """
    if not new.provider or new.provider != old.provider:
        return "different"
    if new.embedding is not None and old.embedding is not None and _cosine(new.embedding, old.embedding) >= SIMILAR:
        return "duplicate"
    # 國家或截止日兩邊都有、卻不一樣：不同的獎學金（例如同一所大學的兩個學程）
    if new.countries and old.countries and new.countries != old.countries:
        return "different"
    if new.closes and old.closes and not new.closes & old.closes:
        return "different"
    if new.countries and new.closes and new.countries == old.countries and new.closes == old.closes:
        return "duplicate"
    return "unclear"


def _cosine(a: list[float], b: list[float]) -> float:
    """語意相似度（兩個向量夾角的餘弦）：1 代表方向完全一樣。"""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
