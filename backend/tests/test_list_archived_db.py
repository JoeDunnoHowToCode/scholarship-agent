"""列表預設不列已封存的獎學金；archived=True 才列（docs/ui-review-2.md 待決定 3 乙、ADR-106）。

真的資料庫，只讀：開發資料庫有 46 筆已封存；CI 的空資料庫沒有，那時只檢查預設不列。
"""

from sqlalchemy import func, select

from app.features.scholarships import api
from app.features.scholarships.models import Scholarship, ScholarshipStatus
from app.shared.db import SessionLocal


def test_list_hides_archived_unless_asked() -> None:
    with SessionLocal() as session:
        archived = session.scalar(
            select(func.count()).where(
                Scholarship.status == ScholarshipStatus.ARCHIVED,
                Scholarship.duplicate_of.is_(None),
                Scholarship.source_id.is_not(None),
            )
        )
        default = api.list_scholarships(session)
        assert all(row.status != "archived" for row in default.rows)
        shown = api.list_scholarships(session, archived=True)
        assert sum(row.status == "archived" for row in shown.rows) == archived
        assert len(shown.rows) == len(default.rows) + archived
