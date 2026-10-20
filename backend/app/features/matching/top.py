"""列出評分前幾名（第 6 天）。

用法：uv run python -m app.features.matching.top [--limit 20]
"""

import argparse

from sqlalchemy import select

from app.features.matching.models import Match
from app.features.profiles.service import CURRENT_USER_ID
from app.features.scholarships.models import Scholarship
from app.shared.db import SessionLocal

LABELS = {"nationality": "國籍", "degree": "學位", "time": "時間"}


def main() -> None:
    parser = argparse.ArgumentParser(description="列出評分前幾名")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    with SessionLocal() as session:
        rows = session.execute(
            select(Match, Scholarship)
            .join(Scholarship, Scholarship.id == Match.scholarship_id)
            .where(Match.user_id == CURRENT_USER_ID)
            .order_by(Match.total.desc())
            .limit(args.limit)
        ).all()
        for rank, (match, row) in enumerate(rows, 1):
            flags = [f"{LABELS[n]}待確認" for n in match.unclear] + [f"{LABELS[n]}不符合" for n in match.failed]
            category = "" if match.category_name == row.name else f"｜{match.category_name}"
            print(f"{rank:>2}. {match.total:5.1f}  {row.name}{category}｜{'、'.join(flags) or '條件都符合'}")
            print(f"       {match.checks['time']['reason']}｜{row.official_url}")


if __name__ == "__main__":
    main()
