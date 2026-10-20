"""評分裡由程式決定的部分（ADR-043、046、047、055）：硬性條件與加權總分。

硬性條件只看國籍、學位、時間，每項回傳 pass（符合）、fail（不符合）或 unclear（待確認），
再交給 scoring.apply_caps 壓總分上限。規則固定的判斷交給程式：每次結果一樣，也不花 AI 費用。
"""

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
