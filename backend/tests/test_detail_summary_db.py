"""詳細頁頁首的重點摘要（UI 計畫 B2、ADR-090）：和列表卡片顯示同一行申請日期、同一句補助。

用開發用的資料庫，只讀不寫（和 test_unreachable_db 一樣在真的資料上跑）。
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.features.profiles.service import CURRENT_USER_ID, get_profile
from app.features.scholarships import api
from app.features.scholarships.models import Scholarship
from app.shared.db import SessionLocal


def test_detail_summary_matches_the_list_card() -> None:
    with SessionLocal() as session:
        rows = session.scalars(
            select(Scholarship)
            .where(Scholarship.duplicate_of.is_(None), Scholarship.source_id.is_not(None))
            .options(selectinload(Scholarship.cycles))
        ).all()
        profile = get_profile(session, CURRENT_USER_ID)
        nationality = profile.nationality if profile else None
        now = datetime.now(UTC)
        checked = 0
        for row in rows[:20]:
            card = api.to_row(row, None, now.date(), nationality, now)
            detail = api.read_scholarship(row.id, session)
            assert detail.deadline_line == card.deadline_line
            assert detail.amount_headline == card.amount_headline
            checked += 1
        assert checked == min(20, len(rows)) > 0
