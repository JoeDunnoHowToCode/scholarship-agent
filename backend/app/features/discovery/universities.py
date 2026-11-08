"""逐校找的學校名單（ADR-083）：載入種子、每天挑一批還沒找過的學校。

用法：uv run python -m app.features.discovery.universities --load   把 universities.csv 載入資料庫
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.features.discovery.models import University

SEED = Path(__file__).with_name("universities.csv")
PER_DAY = 30  # 每天最多找幾所（「Claude 自行決定」第 10 點）
RESEARCH_AFTER = timedelta(days=365)  # 找過一輪後，每所學校每年重找一次


def read_seed(path: Path = SEED) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def load_seed(session: Session, rows: list[dict[str, str]]) -> int:
    """依首頁網址新增或更新學校，回傳新增幾所；重複執行結果一樣（冪等）。呼叫的人負責 commit。"""
    added = 0
    for row in rows:
        school = session.scalars(select(University).where(University.homepage == row["homepage"])).first()
        if school is None:
            school = University(homepage=row["homepage"])
            session.add(school)
            added += 1
        # 空字串存成空白（NULL），和其他欄位一致
        school.country, school.name, school.source_url = row["country"], row["name"], row["source_url"]
        school.region, school.note = row.get("region") or None, row.get("note") or None
    session.flush()
    return added


def todays_batch(session: Session, now: datetime, limit: int = PER_DAY) -> list[University]:
    """今天要找的學校：從沒找過的先，再來是超過一年沒找的。"""
    return list(session.scalars(
        select(University)
        .where(or_(University.last_searched_at.is_(None), University.last_searched_at < now - RESEARCH_AFTER))
        .order_by(University.last_searched_at.asc().nulls_first(), University.id)
        .limit(limit)
    ))


def main() -> None:
    import argparse

    from app.shared.db import SessionLocal

    parser = argparse.ArgumentParser(description="逐校找的學校名單")
    parser.add_argument("--load", action="store_true", help="把 universities.csv 載入資料庫")
    args = parser.parse_args()
    if not args.load:
        parser.error("目前只有 --load")
    rows = read_seed()
    with SessionLocal() as session:
        added = load_seed(session, rows)
        session.commit()
    print(f"種子 {len(rows)} 所，新增 {added} 所")


if __name__ == "__main__":
    main()
