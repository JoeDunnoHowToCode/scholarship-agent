"""產生通知要能在真的資料庫上跑完（11-04 發現：新年度公布的查詢寫錯，收尾工作當掉）。

用開發用的資料庫，在交易裡跑完就復原，不留任何資料；需要已經有個人資料（docker compose 起著）。
"""

from datetime import UTC, datetime

import pytest

from app.features.notifications.generate import generate
from app.features.profiles.service import CURRENT_USER_ID
from app.shared.db import SessionLocal


def test_generate_runs_on_the_real_database() -> None:
    session = SessionLocal()
    try:
        try:
            counts = generate(session, CURRENT_USER_ID, datetime.now(UTC))
        except Exception as error:  # noqa: BLE001 — 任何例外都代表收尾工作會當掉
            pytest.fail(f"generate() 當掉：{type(error).__name__}: {error}")
        assert isinstance(counts, dict)
    finally:
        session.rollback()  # generate 不 commit；這裡復原，不留下事件
        session.close()


def test_a_scholarship_gone_from_its_page_gets_no_notifications() -> None:
    # ADR-108：頁面上不再出現的其他獎學金（extracted.gone）已封存，不能再送「新獎學金」之類的通知
    from sqlalchemy import select

    from app.features.matching.models import Match
    from app.features.notifications.models import Event
    from app.features.scholarships.models import Scholarship
    from app.features.sources.models import Source, SourceKind

    session = SessionLocal()
    try:
        source = Source(name="Test gone notify", url="https://test-gone-notify.example/", kind=SourceKind.UNIVERSITY)
        session.add(source)
        session.flush()
        rows = {
            gone: Scholarship(name=f"Test notify {gone}", source_id=source.id, key=f"k{gone}", countries=["SE"],
                              degrees=["master"], nationality_scope="all", nationalities=[],
                              extracted={"gone": True} if gone else {})
            for gone in (True, False)
        }
        session.add_all(rows.values())
        session.flush()
        session.add_all([Match(user_id=CURRENT_USER_ID, scholarship_id=row.id, category_name="x", total=100,
                               cap=None, checks={}, sub_scores={}, profile_version=1, computed_at=datetime.now(UTC))
                         for row in rows.values()])
        session.flush()
        generate(session, CURRENT_USER_ID, datetime.now(UTC))
        notified = set(session.scalars(select(Event.scholarship_id).where(
            Event.scholarship_id.in_([row.id for row in rows.values()]))))
        assert notified == {rows[False].id}
    finally:
        session.rollback()
        session.close()
