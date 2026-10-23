"""列出評分前幾名（第 6 天）；第 7 天起依時間狀態分組（ADR-059）。

用法：uv run python -m app.features.matching.top [--limit 20]
"""

import argparse

from sqlalchemy import select

from app.features.matching.models import Match
from app.features.profiles.service import CURRENT_USER_ID
from app.features.scholarships.models import Scholarship
from app.shared.db import SessionLocal

LABELS = {"nationality": "國籍", "degree": "學位", "time": "時間"}
# 分數只算適配度，時間不算分（ADR-059）：顯示時先依時間狀態分組，同一組再依分數排
GROUPS = {"pass": "還能申請", "unclear": "時間待確認", "fail": "已截止或不適用"}
ORDER = {result: index for index, result in enumerate(GROUPS)}


def main() -> None:
    parser = argparse.ArgumentParser(description="列出評分前幾名")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    with SessionLocal() as session:
        rows = sorted(
            session.execute(
                select(Match, Scholarship)
                .join(Scholarship, Scholarship.id == Match.scholarship_id)
                .where(Match.user_id == CURRENT_USER_ID)
            ).all(),
            key=lambda pair: (ORDER[pair[0].checks["time"]["result"]], -pair[0].total),
        )
        group = None
        for rank, (match, row) in enumerate(rows[: args.limit], 1):
            if match.checks["time"]["result"] != group:
                group = match.checks["time"]["result"]
                print(f"== {GROUPS[group]}")
            flags = [f"{LABELS[n]}待確認" for n in match.unclear] + [f"{LABELS[n]}不符合" for n in match.failed]
            category = "" if match.category_name == row.name else f"｜{match.category_name}"
            print(f"{rank:>2}. {match.total:5.1f}  {row.name}{category}｜{'、'.join(flags) or '條件都符合'}")
            print(f"       {match.checks['time']['reason']}｜{row.official_url}")


if __name__ == "__main__":
    main()
