"""逐校找的學校名單（ADR-083），在真的資料庫上跑：交易裡跑完就復原。"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.features.discovery.models import University
from app.features.discovery.universities import load_seed, todays_batch
from app.shared.db import SessionLocal

ROWS = [
    {"country": "SE", "region": "", "name": "Test Lund", "homepage": "https://test-lund.example",
     "source_url": "https://www.uka.se/x", "note": ""},
    {"country": "IS", "region": "", "name": "Test Iceland", "homepage": "https://test-hi.example",
     "source_url": "https://www.stjornarradid.is/x", "note": "首頁由人工確認"},
]


def test_loading_the_seed_is_idempotent() -> None:
    session = SessionLocal()
    try:
        assert load_seed(session, ROWS) == 2
        assert load_seed(session, ROWS) == 0  # 再載一次不重複
        renamed = [{**ROWS[0], "name": "Test Lund University"}, ROWS[1]]
        assert load_seed(session, renamed) == 0  # 改名：更新，不新增
        session.flush()
        rows = session.scalars(select(University).where(University.homepage.like("https://test-%")).order_by(University.id)).all()
        assert [(u.country, u.region, u.name, u.note) for u in rows] == [
            ("SE", None, "Test Lund University", None),
            ("IS", None, "Test Iceland", "首頁由人工確認"),
        ]
    finally:
        session.rollback()
        session.close()


def test_todays_batch_takes_never_searched_first_then_older_than_a_year() -> None:
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        load_seed(session, ROWS + [
            {**ROWS[0], "name": "Test Recent", "homepage": "https://test-recent.example"},
            {**ROWS[0], "name": "Test Old", "homepage": "https://test-old.example"},
        ])
        session.flush()
        by_name = {u.name: u for u in session.scalars(select(University).where(University.homepage.like("https://test-%")))}
        for u in by_name.values():
            u.last_searched_at = now - timedelta(days=10)  # 先全部當成最近找過
        by_name["Test Lund"].last_searched_at = None  # 從沒找過
        by_name["Test Old"].last_searched_at = now - timedelta(days=400)  # 超過一年
        session.flush()
        names = [u.name for u in todays_batch(session, now, limit=500) if u.homepage.startswith("https://test-")]
        assert names == ["Test Lund", "Test Old"]  # 最近找過的不挑
        # 數量上限
        assert len(todays_batch(session, now, limit=1)) == 1
    finally:
        session.rollback()
        session.close()
