"""評分裡由程式決定的部分（ADR-043、046、047、055）：硬性條件與加權總分。

硬性條件只看國籍、學位、時間，每項回傳 pass（符合）、fail（不符合）或 unclear（待確認），
再交給 scoring.apply_caps 壓總分上限。規則固定的判斷交給程式：每次結果一樣，也不花 AI 費用。
"""

from dataclasses import dataclass

from app.features.matching.scoring import CheckResult


def nationality_check(user: str, scope: str, codes: list[str]) -> CheckResult:
    """使用者的國籍符不符合國籍範圍（ADR-043）；國碼（例如 TW）不分大小寫比對。"""
    if scope == "all":
        return "pass"
    in_list = user.upper() in [code.upper() for code in codes]
    if scope == "listed":
        return "pass" if in_list else "fail"  # 只限列出的國家
    if scope == "excluded":
        return "fail" if in_list else "pass"  # 列出的國家以外都可以
    return "unclear"  # 原文沒寫國籍資格


@dataclass(frozen=True)  # frozen：建立後不能再改欄位，避免被不小心改掉
class CycleInfo:
    """評分要用到的申請期欄位（ADR-047）。"""

    status: str  # estimated（程式猜的明年日期）／upcoming／open／closed
    nationality_scope: str  # all／listed／excluded
    nationalities: tuple[str, ...]  # 國碼，例如 ("FR", "DE")
    funding: str  # scholarship（申請獎學金）／self_funded（自費）／any（不限）
    verified: bool  # 截止日有沒有通過核對


def applicable(cycles: list[CycleInfo], user: str) -> list[CycleInfo]:
    """這位使用者適用的申請期：國籍符合，而且是給申請獎學金的人（自費生的截止日不算）。"""
    return [
        cycle
        for cycle in cycles
        if nationality_check(user, cycle.nationality_scope, list(cycle.nationalities)) == "pass"
        and cycle.funding in ("scholarship", "any")
    ]


def time_check(cycles: list[CycleInfo], user: str) -> CheckResult:
    """時間來不來得及：只看這位使用者適用的申請期，由上往下判斷。"""
    if not cycles:
        return "unclear"  # 不知道截止日
    mine = applicable(cycles, user)
    if not mine:
        return "fail"  # 有截止日，但沒有一個是給這位使用者的
    still_open = [cycle for cycle in mine if cycle.status in ("open", "upcoming")]
    if any(cycle.verified for cycle in still_open):
        return "pass"
    if still_open or any(cycle.status == "estimated" for cycle in mine):
        return "unclear"  # 截止日沒核對過，或只是程式猜的明年日期
    return "fail"  # 適用的申請期都截止了
