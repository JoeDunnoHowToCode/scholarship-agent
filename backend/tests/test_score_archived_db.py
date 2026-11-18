"""已封存的獎學金不再評分，留著上次的分數（總檢查 D5）。

評分每筆獎學金各自 commit，所以這裡用 savepoint：Session 的 commit 只結束一個 savepoint，
最外層的交易在測試結束時整個復原，真的評分資料不會被動到。個人資料是假的（ADR-087）。
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.matching.models import Match
from app.features.matching.score import score_all
from app.features.profiles.models import Profile
from app.features.scholarships.models import Scholarship, ScholarshipStatus
from app.shared.db import engine

FAKE_USER = 990001  # 不是真的使用者（第一版的使用者固定是 1）
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


class NoAI:
    """沒填科系與領域時評分不會呼叫 AI；真的被呼叫就讓測試失敗。"""

    model = "no-ai"

    def extract(self, prompt: str, schema: type) -> object:
        raise AssertionError("不該呼叫 AI")


def test_an_archived_scholarship_keeps_its_last_score() -> None:
    with engine.connect() as connection:
        outer = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            profile = Profile(user_id=FAKE_USER, nationality="FR", target_degree="master", current_major=None,
                              target_fields=[], target_countries=[], version=1, updated_at=LONG_AGO)
            row = Scholarship(name="Test archived scholarship", source_id=session.scalars(select(Scholarship.source_id)
                              .where(Scholarship.source_id.is_not(None)).limit(1)).one(),
                              key="test-archived-score", status=ScholarshipStatus.ARCHIVED, countries=["FR"],
                              extracted={"categories": [{"name": "Test archived category", "degrees": ["master"]}]})
            session.add_all([profile, row])
            session.flush()
            old = Match(user_id=FAKE_USER, scholarship_id=row.id, category_name="Test archived category", total=42.0,
                        cap=None, checks={}, sub_scores={}, unclear=[], failed=[], profile_version=1,
                        input_hash="old", computed_at=LONG_AGO)
            session.add(old)
            session.flush()

            score_all(session, NoAI(), "no-ai", profile, None)

            kept = session.scalars(
                select(Match).where(Match.user_id == FAKE_USER, Match.scholarship_id == row.id)
            ).all()
            assert [(m.total, m.computed_at) for m in kept] == [(42.0, LONG_AGO)]  # 沒重算、也沒被當成過期刪掉
        finally:
            session.close()
            outer.rollback()
