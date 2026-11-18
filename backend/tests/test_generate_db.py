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


FAKE_USER = 990002  # 不是真的使用者（第一版的使用者固定是 1）


def test_a_scholarship_gone_from_its_page_gets_no_notifications() -> None:
    # ADR-108：頁面上不再出現的其他獎學金（extracted.gone）已封存，不能再送「新獎學金」之類的通知
    # 11-19 使用者選 A：用自己的假使用者與假個人資料（ADR-087），不靠資料庫裡剛好有你的個人資料；
    # 以前 CI 的空資料庫沒有個人資料，generate 一開始就結束，這個測試在 CI 一直失敗
    from sqlalchemy import select

    from app.features.matching.models import Match
    from app.features.notifications.models import Event
    from app.features.profiles.models import Profile
    from app.features.scholarships.models import Scholarship
    from app.features.sources.models import Source, SourceKind

    session = SessionLocal()
    try:
        session.add(Profile(user_id=FAKE_USER, nationality="FR", target_degree="master", version=1,
                            updated_at=datetime.now(UTC)))
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
        session.add_all([Match(user_id=FAKE_USER, scholarship_id=row.id, category_name="x", total=100,
                               cap=None, checks={}, sub_scores={}, profile_version=1, computed_at=datetime.now(UTC))
                         for row in rows.values()])
        session.flush()
        generate(session, FAKE_USER, datetime.now(UTC))
        notified = set(session.scalars(select(Event.scholarship_id).where(
            Event.scholarship_id.in_([row.id for row in rows.values()]))))
        assert notified == {rows[False].id}
    finally:
        session.rollback()
        session.close()
