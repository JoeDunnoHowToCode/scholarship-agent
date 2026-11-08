"""費用摘要指令（ADR-089）。

用法：uv run python -m app.features.costs
"""

from datetime import UTC, datetime

from app.features.costs.summary import summarize
from app.features.costs.usage import NTD_PER_USD
from app.shared.db import SessionLocal
from app.shared.settings import settings


def main() -> None:
    with SessionLocal() as session:
        summary = summarize(session, datetime.now(UTC))
    print(f"本月 AI 費用：約 NT${summary.month_usd * NTD_PER_USD:,.2f}（上限 NT${settings.monthly_cap_ntd:,.0f}）")
    print("\n依功能（本月）：")
    for name, count, usd in summary.by_feature:
        print(f"  {name:<12} {count:>5} 次  約 NT${usd * NTD_PER_USD:,.2f}")
    print("\n最近 7 天（台灣日期）：")
    for day, usd in summary.by_day:
        print(f"  {day:%m-%d}  約 NT${usd * NTD_PER_USD:,.2f}")


if __name__ == "__main__":
    main()
