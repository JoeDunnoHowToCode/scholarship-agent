"""逐校找的學校名單（ADR-083）：載入種子、每天挑一批還沒找過的學校。

用法：uv run python -m app.features.discovery.universities --load   把 universities.csv 載入資料庫
"""

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.features.discovery.models import University

SEED = Path(__file__).with_name("universities.csv")
PER_DAY = 30  # 每天最多找幾所（「Claude 自行決定」第 10 點）


def read_seed(path: Path = SEED) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def load_seed(session: Session, rows: list[dict[str, str]]) -> int:
    """依首頁網址新增或更新學校，回傳新增幾所；重複執行結果一樣（冪等）。呼叫的人負責 commit。"""
    return 0  # 骨架


def todays_batch(session: Session, now: datetime, limit: int = PER_DAY) -> list[University]:
    """今天要找的學校：從沒找過的先，再來是超過一年沒找的。"""
    return []  # 骨架
